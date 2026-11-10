import unittest
from datetime import datetime, timezone
from display_time import ny_time,ny_window
from state.audit import Store
class ProgressTimeTests(unittest.TestCase):
 def test_winter_and_summer_offset(self):
  self.assertIn('08:00 AM EST',ny_time('2026-11-07T13:00:00+00:00'))
  self.assertIn('09:00 AM EDT',ny_time('2026-07-07T13:00:00+00:00'))
 def test_missing_and_naive_time(self):
  self.assertEqual(ny_time(None),'Not recorded')
  with self.assertRaises(ValueError):ny_time(datetime(2026,11,7,13))
 def test_owner_is_not_recording_actor(self):
  s=Store(':memory:');s.status('ED-001','BLOCKED','Dispatcher RW','Check availability','No crew','Follow-up',owner='Supervisor team')
  self.assertEqual(s.progress()['ED-001']['owner'],'Supervisor team')
  self.assertEqual(s.history()[0]['actor'],'Dispatcher RW')
 def test_missing_owner_rejected(self):
  s=Store(':memory:')
  with self.assertRaises(ValueError):s.status('ED-001','BLOCKED','RW','Follow up','No crew','Test',owner=' ')
  self.assertEqual(s.history(),[])
