"""Shared SQLite workflow acceptance and negative tests."""
import sys,unittest,tempfile
from pathlib import Path
from dataclasses import replace
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from models import Proposal
from roster import demo_roster,slots,RULES
from demo_adapter.fixtures import load_fixture
from state.audit import Store,report,csv_export
from integrations import feature_bridge as bridge
from ui.communication import handover_draft

class SharedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(':memory:'); self.store.seed_day()
        self.t=load_fixture()[2]; self.roster=demo_roster(); self.window=slots()[0]
        self.p=Proposal(self.t.ticket_id,('T01','T02'),*self.window)
        self.store.commit(self.p,self.t,self.roster,RULES['CORRECTIVE'],'Dispatcher','Reviewed crew')
        self.person=self.roster[0]
    def tearDown(self): self.store.close()
    def send(self,**kwargs):
        return self.store.send(self.t,self.person,self.roster,'Dispatcher','SIMULATED test work-order message',**kwargs)
    def test_assignment_message_reply_progress_report_share_same_ticket(self):
        m=self.send(); self.assertEqual(m['assignment_group_id'],self.store.assignments()[0]['atomic_group_id'])
        self.store.reply(m['message_id'],'ACKNOWLEDGED','Dispatcher',apply_progress=True)
        self.assertEqual(self.store.progress()[self.t.ticket_id]['status'],'ACKNOWLEDGED')
        row=report([self.t],self.store)[0]
        self.assertEqual(row['messages_sent'],1); self.assertEqual(row['last_reply'],'ACKNOWLEDGED')
        self.assertIn('ACKNOWLEDGED',csv_export([row]))
        self.assertIn(self.t.ticket_id,handover_draft(self.store,[self.t]))
        self.assertEqual([e['event_type'] for e in self.store.history()].count('MESSAGE_REPLY'),1)
    def test_reply_without_apply_keeps_work_status(self):
        m=self.send(); self.store.reply(m['message_id'],'ACKNOWLEDGED','Dispatcher')
        self.assertEqual(self.store.progress()[self.t.ticket_id]['status'],'ASSIGNED')
    def test_cannot_respond_requires_reason_and_blocks_only_on_review(self):
        m=self.send(); before=self.store.history()
        with self.assertRaises(ValueError): self.store.reply(m['message_id'],'CANNOT_RESPOND','Dispatcher',apply_progress=True)
        self.assertEqual(self.store.history(),before); self.assertEqual(self.store.messages()[0]['response'],'')
        self.store.reply(m['message_id'],'CANNOT_RESPOND','Dispatcher','Demo equipment unavailable',True)
        self.assertEqual(self.store.progress()[self.t.ticket_id]['status'],'BLOCKED')
        self.assertIn('unavailable',self.store.progress()[self.t.ticket_id]['blocker'])
    def test_stale_crew_reply_rejected_atomically(self):
        m=self.send(); self.store.commit(replace(self.p,crew=('T01','T10')),self.t,self.roster,RULES['CORRECTIVE'],'Dispatcher','Replace crew',replace=True)
        before=self.store.assignments(),self.store.history()
        with self.assertRaisesRegex(ValueError,'Stale reply'): self.store.reply(m['message_id'],'ACKNOWLEDGED','Dispatcher',apply_progress=True)
        self.assertEqual(before,(self.store.assignments(),self.store.history()))
        self.assertEqual(self.store.messages()[0]['response'],'')
        self.store.reply(m['message_id'],'ACKNOWLEDGED','Dispatcher')
        self.assertEqual(self.store.progress()[self.t.ticket_id]['status'],'ASSIGNED')
    def test_duplicate_reply_is_not_overwritten(self):
        m=self.send(); self.store.reply(m['message_id'],'ACKNOWLEDGED','Dispatcher')
        with self.assertRaises(ValueError): self.store.reply(m['message_id'],'DECLINED','Dispatcher','Changed mind')
        self.assertEqual(self.store.messages()[0]['response'],'ACKNOWLEDGED')
    def test_unknown_absent_and_inactive_recipients_blocked_even_if_urgent(self):
        for fields in ({'attendance':'UNKNOWN'},{'attendance':'ABSENT'},{'active':False}):
            person=replace(self.person,**fields); roster=[person]+self.roster[1:]
            with self.assertRaisesRegex(ValueError,'MESSAGE_BLOCKED_OFF_DUTY'):
                self.store.send(self.t,person,roster,'Dispatcher','Test',True,True)
        self.assertEqual(self.store.messages(),[])
    def test_send_uses_persisted_attendance_not_stale_caller(self):
        person=self.roster[2]
        self.store.attendance(person,'UNKNOWN','Dispatcher')
        with self.assertRaisesRegex(ValueError,'MESSAGE_BLOCKED_OFF_DUTY'):
            self.store.send(self.t,person,self.roster,'Dispatcher','Test')
    def test_conflict_needs_urgent_and_explicit_confirmation_without_preemption(self):
        other=load_fixture()[4]; board=self.store.assignments()
        with self.assertRaisesRegex(ValueError,'MESSAGE_BLOCKED_CONFLICT'):
            self.store.send(other,self.person,self.roster,'Dispatcher','Other work')
        with self.assertRaises(ValueError): self.store.send(other,self.person,self.roster,'Dispatcher','Other work',False,True)
        m=self.store.send(other,self.person,self.roster,'Dispatcher','Other work',True,True)
        self.assertEqual(m['conflict_confirmed_by'],'Dispatcher'); self.assertEqual(board,self.store.assignments())
    def test_current_clock_crossing_shift_boundary_blocks_send(self):
        self.store.advance_clock(8*60,'Dispatcher')
        with self.assertRaisesRegex(ValueError,'MESSAGE_BLOCKED_OFF_DUTY'): self.send()
        self.assertEqual(self.store.messages(),[])
    def test_no_ack_threshold_persisted_and_clears_from_current_followup(self):
        m=self.send(); self.store.advance_clock(14,'Dispatcher')
        self.assertEqual(bridge.overdue(self.store.messages(),self.store.clock()),[])
        self.store.advance_clock(1,'Dispatcher')
        self.assertIn(m['message_id'],bridge.overdue(self.store.messages(),self.store.clock()))
        self.assertIn('NO_ACK',report([self.t],self.store)[0]['message_follow_up'])
        self.store.advance_clock(15,'Dispatcher')
        self.assertEqual(sum(e['event_type']=='NO_ACK' for e in self.store.history()),1)
        self.store.reply(m['message_id'],'ACKNOWLEDGED','Dispatcher')
        self.assertEqual(report([self.t],self.store)[0]['message_follow_up'],'')
    def test_blank_sender_and_body_roll_back(self):
        for actor,body in [('', 'Test'),('Dispatcher','')]:
            with self.assertRaises(ValueError): self.store.send(self.t,self.person,self.roster,actor,body)
        self.assertEqual(self.store.messages(),[])
    def test_advisory_calls_do_not_change_state_or_recommend_split_crews(self):
        before=self.store.assignments(),self.store.history(),self.store.messages()
        self.assertIn(self.t.ticket_id,bridge.draft_message(self.t,self.roster,self.store.assignments(),self.store.clock()))
        bridge.availability(self.t,self.roster,RULES['CORRECTIVE'],*self.window,self.store.assignments())
        bridge.intake(load_fixture()); handover_draft(self.store,load_fixture())
        advice=bridge.explain('CREW_UNAVAILABLE')['next_action']
        self.assertIn('together',advice); self.assertNotIn('split',advice)
        self.assertEqual(before,(self.store.assignments(),self.store.history(),self.store.messages()))
    def test_restart_and_reset_preserve_messages_activity_and_seed(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'shared.db'; s=Store(path); seed=s.seed_day()
            s.commit(self.p,self.t,self.roster,RULES['CORRECTIVE'],'Dispatcher','Reviewed')
            m=s.send(self.t,self.person,self.roster,'Dispatcher','Test'); s.advance_clock(15,'Dispatcher')
            count=len(s.history()); clock=s.clock(); s.close(); s=Store(path)
            self.assertEqual(s.seed_day(),seed); self.assertEqual(s.clock(),clock)
            self.assertEqual(s.messages()[0]['message_id'],m['message_id']); self.assertEqual(len(s.history()),count)
            s.reset('Dispatcher',True); self.assertEqual(s.assignments(),[])
            self.assertEqual(len(s.messages()),1); self.assertGreater(len(s.history()),count); s.close()
