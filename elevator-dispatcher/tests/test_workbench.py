import sys, unittest, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataclasses import replace
from datetime import timedelta
from models import Proposal
from roster import demo_roster, slots, RULES, BOROUGHS
from validators import validate
from demo_adapter.fixtures import load_fixture
from demo_adapter.scheduler import recommend
from state.audit import Store, report, csv_export

class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.s=Store(':memory:'); self.ts=load_fixture(); self.r=demo_roster(); self.t=self.ts[2]; self.rule=RULES['CORRECTIVE']; self.p=Proposal(self.t.ticket_id,('T01','T02'),*slots()[0])
    def commit(self,p=None,t=None,r=None,**kw): self.s.commit(p or self.p,t or self.t,r or self.r,self.rule,'QA','Test decision',**kw)
    def test_unknown_absent_inactive_offshift(self):
        for change in [{'attendance':'UNKNOWN'},{'attendance':'ABSENT'},{'active':False},{'shift_end':slots()[0][0]}]:
            r=[replace(p,**change) if p.technician_id=='T02' else p for p in self.r]
            with self.assertRaises(ValueError): self.commit(r=r)
            self.assertEqual(self.s.assignments(),[])
    def test_partial_duplicate_and_unknown_crew(self):
        for crew in [('T01',),('T01','T01'),('T01','MISSING')]:
            with self.assertRaises(ValueError): self.commit(replace(self.p,crew=crew))
        self.assertEqual(self.s.history(),[])
    def test_qualification_expiry_and_verification(self):
        for changes in [{'qualifications':()},{'certification_status':'UNVERIFIED'},{'certification_expiry':self.p.start}]:
            with self.assertRaises(ValueError): self.commit(r=[replace(p,**changes) if p.technician_id=='T02' else p for p in self.r])
    def test_demo_borough_coverage(self):
        self.assertEqual(set(BOROUGHS), {b for p in self.r for b in p.sectors})
        self.assertTrue(all(t.sector in BOROUGHS for t in self.ts))
        self.assertEqual(self.r[0].sectors, ('Manhattan',))
        self.assertEqual(self.r[-1].sectors, BOROUGHS)
    def test_area_and_depot(self):
        for change in [{'sector':'EAST'},{'depot':'OTHER'}]:
            t=replace(self.t,**change)
            with self.assertRaises(ValueError): self.commit(t=t)
    def test_overlap_atomic_rollback(self):
        self.commit(); old=self.s.assignments(); n=len(self.s.history())
        t=self.ts[4]
        with self.assertRaises(ValueError): self.commit(replace(self.p,ticket_id=t.ticket_id),t)
        self.assertEqual(old,self.s.assignments()); self.assertEqual(n,len(self.s.history()))
    def test_reassignment_failure_preserves_old(self):
        self.commit(); old=self.s.assignments()
        with self.assertRaises(ValueError): self.commit(replace(self.p,crew=('T01',)),replace=True)
        self.assertEqual(old,self.s.assignments())
    def test_adjacent_slots_allowed(self):
        self.commit(); t=self.ts[4]; self.commit(Proposal(t.ticket_id,('T01','T02'),*slots()[1]),t)
        self.assertEqual(len(self.s.assignments()),2)
    def test_remove_and_reset_audit(self):
        self.commit(); self.s.remove(self.t.ticket_id,'QA','Remove crew'); self.assertEqual(self.s.assignments(),[])
        self.commit()
        with self.assertRaises(ValueError): self.s.reset('QA')
        before=len(self.s.history()); self.s.reset('QA',True)
        self.assertGreater(len(self.s.history()),before); self.assertEqual(len(report(self.ts,self.s)),12)
    def test_hazard_invalid_and_non_demo_blocked(self):
        for t in (self.ts[1],self.ts[10]):
            with self.assertRaises(ValueError): self.commit(replace(self.p,ticket_id=t.ticket_id),t)
        self.assertIn('REAL_WORLD_ELIGIBILITY_UNVERIFIED',validate(self.p,self.t,self.r,self.rule,[],mode='LIVE'))
    def test_determinism_and_float(self):
        a=recommend(self.ts,self.r,RULES,slots(),[]); b=recommend(list(reversed(self.ts)),list(reversed(self.r)),RULES,slots(),[])
        self.assertEqual(a,b)
        self.assertTrue(any('T10' in p.crew for p in a[0]))
        self.assertIn('HAZARD_REVIEW_REQUIRED',a[1]['ED-002'])
    def test_status_reports_and_csv(self):
        with self.assertRaises(ValueError): self.s.status(self.t.ticket_id,'EN_ROUTE','QA','Go','','Reason')
        self.commit()
        for status in ['RESTORED','CLOSED']: self.s.status(self.t.ticket_id,status,'QA','Review official closure','','Reported')
        self.assertEqual(self.s.progress()[self.t.ticket_id]['status'],'CLOSED')
        self.assertEqual(len([e for e in self.s.history() if e['event_type']=='STATUS']),3)
        self.assertIn('next_action',csv_export(report(self.ts,self.s)))
        self.assertIn("'=SUM",csv_export([{'value':'=SUM(1)'}]))
    def test_failed_actor_rolls_back(self):
        with self.assertRaises(ValueError): self.s.commit(self.p,self.t,self.r,self.rule,'','Reason')
        self.assertEqual(self.s.assignments(),[])
    def test_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'test.db'); s.event('TEST','seed','QA',None,{},'Test')
            self.assertEqual(len(Store(Path(d)/'test.db').history()),1)

if __name__=='__main__': unittest.main()
