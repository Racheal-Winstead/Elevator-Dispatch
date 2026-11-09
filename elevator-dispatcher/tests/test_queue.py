import unittest
from demo_adapter.fixtures import load_fixture
from work_queue import queue_rows, demo_work_order
class QueueTests(unittest.TestCase):
 def setUp(self): self.tickets=load_fixture()
 def test_unique_demo_numbers(self):
  ids=[demo_work_order(t) for t in self.tickets]
  self.assertEqual(len(ids),len(set(ids)))
  self.assertTrue(all(i.isdigit() for i in ids))
 def test_search_number_and_internal_id(self):
  self.assertEqual(queue_rows(self.tickets,{},search='900000003')[0]['Internal ID'],'ED-003')
  self.assertEqual(len(queue_rows(self.tickets,{},search='ed-003')),1)
 def test_missing_data_remains_visible(self):
  rows=queue_rows(self.tickets,{},quality='NEEDS_REVIEW')
  self.assertIn('ED-011',[r['Internal ID'] for r in rows])
  self.assertIn('MISSING',next(r for r in rows if r['Internal ID']=='ED-011')['Building'])
  self.assertNotIn('ED-011',[r['Internal ID'] for r in queue_rows(self.tickets,{},quality='READY')])
 def test_borough_and_status(self):
  rows=queue_rows(self.tickets,{'ED-003':{'status':'ASSIGNED'}},borough='Manhattan',status='ASSIGNED')
  self.assertEqual([r['Internal ID'] for r in rows],['ED-003'])
 def test_empty_search_does_not_mutate_source(self):
  self.assertEqual(queue_rows(self.tickets,{},search='no-such-work-order'),[])
  self.assertEqual(len(self.tickets),12)
if __name__=='__main__':unittest.main()
