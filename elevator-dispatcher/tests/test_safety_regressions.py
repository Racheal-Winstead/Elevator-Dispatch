import sys, unittest
from pathlib import Path
from datetime import timedelta, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from models import Proposal
from roster import demo_roster,slots,RULES
from demo_adapter.fixtures import load_fixture
from state.audit import Store

class SafetyRegressions(unittest.TestCase):
    def setUp(self):
        self.store=Store(':memory:'); self.tickets=load_fixture(); self.roster=demo_roster(); self.rule=RULES['CORRECTIVE']
        self.p=Proposal(self.tickets[2].ticket_id,('T01','T02'),*slots()[0])
        self.store.commit(self.p,self.tickets[2],self.roster,self.rule,'QA','Seed assignment')
    def tearDown(self): self.store.close()
    def test_mixed_timezone_overlap_rejected_without_state_or_history_change(self):
        offset=timezone(timedelta(hours=-5))
        p=Proposal(self.tickets[4].ticket_id,self.p.crew,(self.p.start+timedelta(hours=1)).astimezone(offset),(self.p.end+timedelta(hours=1)).astimezone(offset))
        before=self.store.assignments(),self.store.history()
        with self.assertRaisesRegex(ValueError,'MANUAL_CONFLICT'):
            self.store.commit(p,self.tickets[4],self.roster,self.rule,'QA','Conflicting offset')
        self.assertEqual(before,(self.store.assignments(),self.store.history()))
    def test_unassigned_status_cannot_leave_a_committed_crew(self):
        before=self.store.assignments(),self.store.progress(),self.store.history()
        with self.assertRaisesRegex(ValueError,'Remove the complete assignment'):
            self.store.status(self.p.ticket_id,'UNASSIGNED','QA','Review','','Status only')
        self.assertEqual(before,(self.store.assignments(),self.store.progress(),self.store.history()))
    def test_naive_window_rejected_cleanly(self):
        from dataclasses import replace
        with self.assertRaisesRegex(ValueError,'INVALID_TIME_WINDOW'):
            self.store.commit(replace(self.p,start=self.p.start.replace(tzinfo=None)),self.tickets[2],self.roster,self.rule,'QA','Bad time',replace=True)
    def test_offset_adjacent_window_allowed_and_stored_as_utc(self):
        offset=timezone(timedelta(hours=-5))
        start,end=self.p.end,self.p.end+timedelta(hours=2)
        p=Proposal(self.tickets[4].ticket_id,self.p.crew,start.astimezone(offset),end.astimezone(offset))
        self.store.commit(p,self.tickets[4],self.roster,self.rule,'QA','Adjacent offset window')
        actual=next(a for a in self.store.assignments() if a['ticket_id']==p.ticket_id)
        self.assertEqual(actual['start'],start.isoformat()); self.assertEqual(actual['end'],end.isoformat())
    def test_invalid_existing_timestamp_fails_closed(self):
        from validators import validate
        malformed=[{'ticket_id':'BAD','crew':list(self.p.crew),'start':'not a timestamp','end':self.p.end.isoformat()}]
        self.assertIn('INVALID_TIME_WINDOW',validate(self.p,self.tickets[2],self.roster,self.rule,malformed))
    def test_remove_changes_status_and_bookings_atomically(self):
        before=len(self.store.history())
        self.store.remove(self.p.ticket_id,'QA','Unassign whole crew')
        self.assertEqual(self.store.assignments(),[])
        self.assertEqual(self.store.progress()[self.p.ticket_id]['status'],'UNASSIGNED')
        self.assertEqual(len(self.store.history()),before+2)
