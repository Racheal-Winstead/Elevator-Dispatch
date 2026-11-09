"""Local SQLite transactions. Append-only events through this application API."""
import csv, io, json, sqlite3, uuid
from datetime import datetime, timezone
from models import STATUSES
from validators import validate
from time_windows import window

def now(): return datetime.now(timezone.utc).isoformat()
class Store:
    def __init__(self,path):
        self.db=sqlite3.connect(str(path),isolation_level=None,check_same_thread=False)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS assignments(ticket_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS progress(ticket_id TEXT PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, timestamp TEXT, actor TEXT,event_type TEXT,entity_id TEXT,old_value TEXT,new_value TEXT,reason TEXT);''')
    def close(self):
        self.db.close()
    def __del__(self):
        # Each Store owns one connection; release it when a rerun replaces the Store.
        if hasattr(self, 'db'):
            self.db.close()
    def event(self,kind,entity,actor,old,new,reason):
        if not actor.strip() or not reason.strip(): raise ValueError('Actor and reason are required')
        self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),now(),actor,kind,entity,json.dumps(old),json.dumps(new),reason))
    def assignments(self): return [json.loads(r[0]) for r in self.db.execute('SELECT data FROM assignments ORDER BY ticket_id')]
    def history(self):
        cur=self.db.execute('SELECT * FROM events ORDER BY rowid DESC')
        return [dict(zip([c[0] for c in cur.description],r)) for r in cur.fetchall()]
    def progress(self): return {r[0]:json.loads(r[1]) for r in self.db.execute('SELECT ticket_id,data FROM progress')}
    def commit(self,proposal,t,roster,rule,actor,reason,replace=False):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old=next((a for a in self.assignments() if a['ticket_id']==t.ticket_id),None)
            board=[a for a in self.assignments() if not(replace and a['ticket_id']==t.ticket_id)]
            errors=validate(proposal,t,roster,rule,board)
            if errors: raise ValueError(', '.join(errors))
            start,end=window(proposal.start,proposal.end)
            data={'ticket_id':t.ticket_id,'crew':list(proposal.crew),'start':start.isoformat(),'end':end.isoformat(),'atomic_group_id':str(uuid.uuid4()),'rule_version':proposal.rule_version,'scheduler_source':proposal.scheduler_source,'engine_rule_version':proposal.engine_rule_version,'engine_commit':proposal.engine_commit}
            self.db.execute('INSERT OR REPLACE INTO assignments VALUES(?,?)',(t.ticket_id,json.dumps(data)))
            self._status(t.ticket_id,'ASSIGNED',actor,'Confirm field acknowledgement','',reason)
            self.event('REASSIGN' if old else 'ASSIGN',t.ticket_id,actor,old,data,reason)
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK'); raise
    def _status(self,tid,status,actor,next_action,blocker,reason,owner=None):
        old=self.progress().get(tid)
        data={'status':status,'owner':owner if owner is not None else actor,'last_update':now(),'next_action':next_action,'blocker':blocker,'source':'DISPATCHER_ENTERED'}
        self.db.execute('INSERT OR REPLACE INTO progress VALUES(?,?)',(tid,json.dumps(data)))
        self.event('STATUS',tid,actor,old,data,reason)
    def status(self,tid,status,actor,next_action,blocker,reason,owner=None):
        if owner is not None and not owner.strip(): raise ValueError('Responsible owner is required')
        if status not in STATUSES: raise ValueError('Unknown status')
        if not next_action.strip(): raise ValueError('Next action is required')
        if status=='BLOCKED' and not blocker.strip(): raise ValueError('Blocker is required')
        with self.transaction():
            has_crew=any(a['ticket_id']==tid for a in self.assignments())
            if status=='UNASSIGNED' and has_crew: raise ValueError('Remove the complete assignment before marking UNASSIGNED')
            if status not in ('UNASSIGNED','BLOCKED') and not has_crew: raise ValueError('Assign a complete crew first')
            self._status(tid,status,actor,next_action,blocker,reason,owner)
    def transaction(self):
        from contextlib import contextmanager
        @contextmanager
        def tx():
            self.db.execute('BEGIN IMMEDIATE')
            try: yield; self.db.execute('COMMIT')
            except Exception: self.db.execute('ROLLBACK'); raise
        return tx()
    def remove(self,tid,actor,reason):
        with self.transaction():
            old=next((a for a in self.assignments() if a['ticket_id']==tid),None)
            if not old: raise ValueError('No assignment')
            self.db.execute('DELETE FROM assignments WHERE ticket_id=?',(tid,))
            self._status(tid,'UNASSIGNED',actor,'Review crew availability','',reason)
            self.event('REMOVE',tid,actor,old,None,reason)
    def reset(self,actor,confirmed=False):
        if not confirmed: raise ValueError('Reset confirmation required')
        with self.transaction():
            old=self.assignments()
            for a in old: self._status(a['ticket_id'],'UNASSIGNED',actor,'Review after schedule reset','','Confirmed schedule reset')
            self.db.execute('DELETE FROM assignments')
            self.event('RESET','schedule',actor,old,[],'Confirmed schedule reset; tickets and audit retained')

def report(tickets,store):
    board={a['ticket_id']:a for a in store.assignments()}; progress=store.progress(); rows=[]
    for t in tickets:
        p=progress.get(t.ticket_id,{'status':'UNASSIGNED','owner':'Dispatcher review','last_update':t.created_at.isoformat(),'next_action':'Review and assign or escalate','blocker':'','source':'SYNTHETIC_DEFAULT'})
        a=board.get(t.ticket_id,{})
        rows.append({'ticket_id':t.ticket_id,'building':t.building,'crew':', '.join(a.get('crew',[])),'start':a.get('start',''),'end':a.get('end',''),'scheduler_source':a.get('scheduler_source',''),'engine_rule_version':a.get('engine_rule_version',''),'engine_commit':a.get('engine_commit',''),**p})
    return rows

def csv_export(rows):
    if not rows: return ''
    out=io.StringIO(); writer=csv.DictWriter(out,fieldnames=list(rows[0])); writer.writeheader()
    for row in rows:
        writer.writerow({k:("'"+str(v) if str(v).startswith(('=','+','-','@')) else v) for k,v in row.items()})
    return out.getvalue()
