"""Contract and negative tests against the real pinned upstream scheduler."""
import sys, unittest, tempfile
from pathlib import Path
from dataclasses import replace
from datetime import timedelta, timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integrations import deshawn_adapter as adapter
from models import Proposal, CrewRule
from roster import demo_roster, slots, RULES
from demo_adapter.fixtures import load_fixture
from state.audit import Store,report,csv_export
from validators import validate

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tickets=load_fixture(); self.roster=demo_roster(); self.windows=slots()
    def recommend(self,**kwargs):
        data=dict(tickets=self.tickets,roster=self.roster,rules=RULES,windows=self.windows,assignments=[])
        data.update(kwargs); return adapter.recommend(**data)
    def test_field_and_role_mapping_preserve_ids_and_no_keyword_emergency(self):
        t=self.tickets[1]; row=adapter.ticket_to_engine(t)
        self.assertEqual(row['ticket_id'],t.ticket_id); self.assertEqual(row['source_record_id'],t.source_record_id)
        self.assertEqual(row['borough'],t.sector); self.assertEqual(row['work_type'],'Elevator outage')
        self.assertEqual(row['hazard_confirmed'],'N')
        staff=adapter.staff_to_engine(self.roster[0],*self.windows[0])
        self.assertEqual(staff['tech_id'],'T01'); self.assertEqual(staff['role'],'Mechanic')
    def test_engine_really_called_and_preview_does_not_mutate_inputs(self):
        engine=adapter.load_engine()
        with patch.object(engine,'auto_schedule',wraps=engine.auto_schedule) as schedule:
            with patch.object(adapter,'load_engine',return_value=engine):
                board=[]; first=self.recommend(assignments=board)
            self.assertGreater(schedule.call_count,0)
        self.assertEqual(board,[])
        self.assertEqual(first,self.recommend(tickets=list(reversed(self.tickets)),roster=list(reversed(self.roster))))
        self.assertTrue(first[0]); self.assertTrue(all(p.scheduler_source==adapter.SOURCE for p in first[0]))
        self.assertIn('HAZARD_REVIEW_REQUIRED',first[1]['ED-002'])
        self.assertIn('INVALID_TICKET_DATA',first[1]['ED-011'])
    def test_every_preview_passes_local_rules_and_capacity(self):
        proposals,_=self.recommend(); shadow=[]
        for p in proposals:
            t=next(t for t in self.tickets if t.ticket_id==p.ticket_id)
            self.assertEqual(validate(p,t,self.roster,RULES[t.work_type],shadow),[])
            shadow.append({'ticket_id':t.ticket_id,'crew':p.crew,'start':p.start.isoformat(),'end':p.end.isoformat()})
    def test_unverified_present_cannot_bypass_upstream_gap(self):
        t=self.tickets[2]
        roster=[self.roster[0],replace(self.roster[1],certification_status='UNVERIFIED')]
        p,e=self.recommend(tickets=[t],roster=roster)
        self.assertEqual(p,[]); self.assertIn('QUALIFICATION_UNVERIFIED',e[t.ticket_id])
    def test_depot_missing_qualification_and_expiry_blocked(self):
        t=self.tickets[2]
        for fields in ({'depots':('OTHER',)},{'qualifications':()},{'certification_expiry':self.windows[0][0]+timedelta(minutes=30)}):
            p,e=self.recommend(tickets=[t],roster=[self.roster[0],replace(self.roster[1],**fields)])
            self.assertEqual(p,[]); self.assertTrue(e[t.ticket_id])
    def test_unknown_and_absent_attendance_not_offered(self):
        for att in ['UNKNOWN','ABSENT','UNAVAILABLE','OFF_SHIFT']:
            p,_=self.recommend(tickets=[self.tickets[2]],roster=[self.roster[0],replace(self.roster[1],attendance=att)])
            self.assertEqual(p,[])
    def test_arbitrary_existing_overlap_maps_to_slot_even_with_offset(self):
        start,end=self.windows[0]; offset=timezone(timedelta(hours=-5))
        a={'ticket_id':'CARRYOVER','crew':['T01','T02'],'start':(start+timedelta(minutes=30)).astimezone(offset).isoformat(),'end':end.astimezone(offset).isoformat()}
        p,_=self.recommend(tickets=[self.tickets[2]],roster=self.roster[:2],windows=[self.windows[0]],assignments=[a])
        self.assertEqual(p,[])
    def test_overlapping_named_windows_cannot_double_book(self):
        start,end=self.windows[0]
        p,e=self.recommend(tickets=[self.tickets[2],self.tickets[4]],roster=self.roster[:2],windows=[(start,end),(start+timedelta(hours=1),end+timedelta(hours=1))])
        self.assertEqual(len(p),1); self.assertEqual(len(e),1)
    def test_unknown_work_type_and_changed_crew_rule_fail_closed(self):
        t=self.tickets[2]
        p,e=self.recommend(tickets=[replace(t,work_type='OTHER')]); self.assertEqual(p,[]); self.assertIn('UNKNOWN_WORK_TYPE',e[t.ticket_id])
        p,e=self.recommend(tickets=[t],rules={'CORRECTIVE':CrewRule(('MECHANIC',))})
        self.assertEqual(p,[]); self.assertIn('ENGINE_RULE_MISMATCH',e[t.ticket_id])
    def test_duplicate_ids_and_unsupported_time_not_silently_coerced(self):
        p,e=self.recommend(tickets=[self.tickets[2]]*2); self.assertEqual(p,[]); self.assertIn('DUPLICATE_TICKET_ID',e[self.tickets[2].ticket_id])
        start,end=self.windows[0]
        p,e=self.recommend(windows=[(start.replace(tzinfo=None),end)])
        self.assertEqual(p,[]); self.assertTrue(all('ENGINE_INPUT_INVALID' in codes for codes in e.values()))
        p,e=self.recommend(windows=[(start,end+timedelta(days=1))]); self.assertEqual(p,[])
        self.assertTrue(all('ENGINE_WINDOW_UNSUPPORTED' in codes for codes in e.values()))
    def test_invalid_upstream_output_is_not_saved_or_returned(self):
        engine=adapter.load_engine()
        with patch.object(engine,'auto_schedule',return_value=[{'ticket_id':'WRONG','slot':'LOCAL-1','crew':{'Mechanic':'T01','Helper':'T02'}}]):
            with patch.object(adapter,'load_engine',return_value=engine):
                p,e=self.recommend(tickets=[self.tickets[2]])
        self.assertEqual(p,[]); self.assertIn('ENGINE_TICKET_MISMATCH',e[self.tickets[2].ticket_id])
    def test_private_engine_configuration_is_isolated(self):
        engine=adapter.load_engine(); before=dict(engine.SLOTS)
        self.recommend()
        self.assertEqual(engine.SLOTS,before)
        self.assertEqual(adapter.load_engine().SLOTS,before)
    def test_preview_stale_after_roster_change_is_rejected_on_commit(self):
        p,_=self.recommend(tickets=[self.tickets[2]])
        roster=[replace(person,attendance='UNKNOWN') if person.technician_id in p[0].crew else person for person in self.roster]
        store=Store(':memory:')
        with self.assertRaises(ValueError): store.commit(p[0],self.tickets[2],roster,RULES['CORRECTIVE'],'QA','Stale preview')
        self.assertEqual(store.assignments(),[]); self.assertEqual(store.history(),[]); store.close()
    def test_preview_commit_progress_export_restart_and_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'demo.db'); p,_=self.recommend(tickets=[self.tickets[2]])
            self.assertEqual(store.assignments(),[])
            store.commit(p[0],self.tickets[2],self.roster,RULES['CORRECTIVE'],'Recorder','Reviewed engine preview')
            a=store.assignments()[0]
            self.assertEqual(a['scheduler_source'],adapter.SOURCE)
            self.assertEqual(a['engine_rule_version'],'demo-rules-v0.1')
            store.status(p[0].ticket_id,'ACKNOWLEDGED','Recorder','Await arrival','','Crew acknowledged',owner='Demo crew lead')
            self.assertIn('Demo crew lead',csv_export(report(self.tickets,store)))
            count=len(store.history()); store.close(); store=Store(Path(folder)/'demo.db')
            self.assertEqual(len(store.history()),count)
            self.assertEqual(store.progress()[p[0].ticket_id]['owner'],'Demo crew lead')
            store.reset('Recorder',True); self.assertEqual(store.assignments(),[])
            self.assertGreater(len(store.history()),count); store.close()
    def test_vendor_matches_upstream_blob_and_checksum_mismatch_blocks(self):
        import hashlib
        data=(adapter.ROOT/'deshawn_engine.py').read_bytes()
        self.assertEqual(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),'6b13cc6f121b65036eb8e78663546dbe409b9ee2')
        with patch.object(adapter,'load_engine',side_effect=adapter.AdapterError('ENGINE_SNAPSHOT_MISMATCH')):
            proposals,exceptions=self.recommend()
        self.assertEqual(proposals,[])
        self.assertTrue(all('ENGINE_SNAPSHOT_MISMATCH' in codes for codes in exceptions.values()))
    def test_missing_snapshot_returns_visible_reason_without_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(adapter,'ROOT',Path(folder)):
                p,e=self.recommend()
        self.assertEqual(p,[])
        self.assertTrue(all('ENGINE_SNAPSHOT_UNAVAILABLE' in codes for codes in e.values()))
