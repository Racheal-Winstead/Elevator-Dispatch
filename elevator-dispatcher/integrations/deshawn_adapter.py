"""Adapt local demo models to a pinned upstream scheduler; never persist here.

Upstream globals are configured only on a fresh, private module instance per
request. Its app, ingestion transport and messaging paths are never executed.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import pandas as pd
from models import Proposal
from time_windows import utc, window, overlaps
from validators import eligible, ticket_errors, validate

ROOT=Path(__file__).parent/'vendor'
ENGINE_COMMIT='6aff6485ae97a8166beaf15678fa3bbf3f0edbb3'
SOURCE='DESHAWN_PINNED_ENGINE'
ROLE_MAP={'MECHANIC':'Mechanic','HELPER':'Helper'}
WORK_TYPE_MAP={'CORRECTIVE':'Elevator outage','INSPECTION':'Planned maintenance',
               'Elevator outage':'Elevator outage','Door fault':'Door fault',
               'Degraded operation':'Degraded operation','Planned maintenance':'Planned maintenance'}

class AdapterError(ValueError): pass

def load_engine():
    """Verify vendored provenance, then load without changing another module."""
    source=ROOT/'deshawn_engine.py'
    try:
        manifest=json.loads((ROOT/'SOURCE.json').read_text())
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        matches=manifest['commit']==ENGINE_COMMIT and digest==manifest['sha256']
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise AdapterError('ENGINE_SNAPSHOT_UNAVAILABLE') from exc
    if not matches: raise AdapterError('ENGINE_SNAPSHOT_MISMATCH')
    spec=importlib.util.spec_from_file_location('_private_dispatch_engine',source)
    engine=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine

def ticket_to_engine(t):
    work_type=WORK_TYPE_MAP.get(t.work_type)
    if not work_type: raise AdapterError('UNKNOWN_WORK_TYPE')
    return {'ticket_id':t.ticket_id,'source_record_id':t.source_record_id,
            'reported_at':utc(t.created_at).replace(tzinfo=None).isoformat(sep=' '),
            'work_type':work_type,'description':t.description,'development':t.building,
            'building':t.building,'borough':t.sector,'elevator_asset_id':t.asset,
            'source_priority':str(t.priority),'no_service':'Y' if t.critical else 'N',
            'senior_building':'N','hazard_confirmed':'N'}

def staff_to_engine(p,start,end):
    """Only called for staff already passing exact local slot/qualification checks."""
    if p.role not in ROLE_MAP: raise AdapterError('ENGINE_ROLE_MISMATCH')
    day=utc(start).date()
    shift_start,shift_end=window(p.shift_start,p.shift_end)
    return {'tech_id':p.technician_id,'name':p.alias,'role':ROLE_MAP[p.role],
            'active':'Y' if p.active else 'N','attendance_state':p.attendance,
            'shift_start':shift_start.strftime('%H:%M') if shift_start.date()==day else '00:00',
            'shift_end':shift_end.strftime('%H:%M') if shift_end.date()==day else '23:59',
            'authorized_boroughs':'|'.join(p.sectors),'boroughs':list(p.sectors),
            'depot':'|'.join(p.depots),'float_helper':'Y' if len(p.sectors)>1 and p.role=='HELPER' else 'N',
            'certification_status':p.certification_status.replace('_','-'),
            'certification_expiry':utc(p.certification_expiry).date().isoformat() if p.certification_expiry else ''}

def commitments_to_engine(assignments,roster,start,end,slot):
    """Map every actual overlap into this engine slot, including arbitrary windows."""
    people={p.technician_id:p for p in roster}; result=[]
    for index,a in enumerate(assignments):
        if not overlaps(start,end,a['start'],a['end']): continue
        crew={}
        for tid in a['crew']:
            if tid not in people or people[tid].role not in ROLE_MAP: raise AdapterError('ENGINE_COMMITMENT_UNMAPPABLE')
            role=ROLE_MAP[people[tid].role]
            if role in crew: raise AdapterError('ENGINE_COMMITMENT_UNMAPPABLE')
            crew[role]=tid
        result.append({'group_id':f'EXISTING-{index}','ticket_id':a['ticket_id'],'slot':slot,'crew':crew})
    return result

def proposal_from_engine(group,t,start,end,engine):
    if group.get('ticket_id')!=t.ticket_id: raise AdapterError('ENGINE_TICKET_MISMATCH')
    reverse={value:key for key,value in ROLE_MAP.items()}
    try:
        roles={reverse[role]:tid for role,tid in group['crew'].items()}
        crew=tuple(roles[role] for role in sorted(roles))
    except (KeyError,TypeError) as exc: raise AdapterError('ENGINE_CREW_INVALID') from exc
    return Proposal(t.ticket_id,crew,start,end,
        explanation='Deshawn’s pinned scheduler selected a complete crew after local attendance, qualification, borough/depot and interval checks. Dispatcher review is required.',
        scheduler_source=SOURCE,engine_rule_version=engine.RULE_VERSION,engine_commit=ENGINE_COMMIT)

def recommend(tickets,roster,rules,windows,assignments):
    """Same local callable contract; pinned engine output is a validated preview."""
    proposals=[]; exceptions={}; shadow=deepcopy(assignments)
    pending=[t for t in tickets if not any(a['ticket_id']==t.ticket_id for a in assignments)]
    try:
        if len({t.ticket_id for t in tickets})!=len(tickets): raise AdapterError('DUPLICATE_TICKET_ID')
        if len({p.technician_id for p in roster})!=len(roster): raise AdapterError('DUPLICATE_TECHNICIAN_ID')
        windows=sorted(window(*w) for w in windows)
        # Upstream uses minute-resolution clock strings. Reject lossy conversions.
        for start,end in windows:
            if start.date()!=end.date() or start.second or end.second or start.microsecond or end.microsecond:
                raise AdapterError('ENGINE_WINDOW_UNSUPPORTED')
        engine=load_engine()
        ready=[]
        for t in pending:
            errors=ticket_errors(t)
            rule=rules.get(t.work_type)
            if not rule or t.work_type not in WORK_TYPE_MAP: errors.append('UNKNOWN_WORK_TYPE')
            elif Counter(ROLE_MAP.get(role,role) for role in rule.roles)!=Counter(engine.CREW_RULES[WORK_TYPE_MAP[t.work_type]]): errors.append('ENGINE_RULE_MISMATCH')
            if errors: exceptions[t.ticket_id]=sorted(set(errors))
            else: ready.append(t)
        if not ready: return proposals,exceptions
        raw=pd.DataFrame([ticket_to_engine(t) for t in ready])
        frame,_=engine.load_tickets(raw=raw)
        frame=engine.with_triage(frame,set())
        ordered=engine.priority_order(frame)
        by_ticket={t.ticket_id:t for t in ready}
        for row in ordered.to_dict('records'):
            t=by_ticket[row['ticket_id']]; rule=rules[t.work_type]; reasons=set(); found=None
            for index,(start,end) in enumerate(windows):
                slot=f'LOCAL-{index+1}'
                engine.SLOTS={slot:(start.strftime('%H:%M'),end.strftime('%H:%M'))}
                engine.DEMO_NOW=pd.Timestamp(start.replace(tzinfo=None))
                usable=[]
                for p in roster:
                    if p.role not in rule.roles: continue
                    errors=eligible(p,t,start,end,rule)
                    if errors: reasons.update(errors)
                    else: usable.append(staff_to_engine(p,start,end))
                board=commitments_to_engine(shadow,roster,start,end,slot)
                groups=engine.auto_schedule(pd.DataFrame([row]),usable,board)
                if not groups:
                    reasons.update(code for code,_ in engine.explain_unassigned(row,board,usable))
                    continue
                if len(groups)!=1 or groups[0].get('slot')!=slot: raise AdapterError('ENGINE_OUTPUT_INVALID')
                candidate=proposal_from_engine(groups[0],t,start,end,engine)
                errors=validate(candidate,t,roster,rule,shadow)
                if errors: reasons.update(errors); continue
                found=candidate; break
            if found:
                proposals.append(found)
                shadow.append({'ticket_id':t.ticket_id,'crew':list(found.crew),'start':found.start.isoformat(),'end':found.end.isoformat()})
            else: exceptions[t.ticket_id]=sorted(reasons or {'NO_CAPACITY'})
        return proposals,exceptions
    except (AdapterError,ValueError,KeyError,TypeError) as exc:
        # No silent fixture fallback and no partially returned plan on conversion failure.
        code=str(exc) if isinstance(exc,AdapterError) else 'ENGINE_INPUT_INVALID'
        return [],{t.ticket_id:sorted(set(ticket_errors(t)+[code])) for t in pending}
