"""Building-local car labels must not create false duplicate advice."""
import sys,unittest
from pathlib import Path
from dataclasses import replace
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from demo_adapter.fixtures import load_fixture
from integrations.feature_bridge import intake
class IntakeIdentityTests(unittest.TestCase):
    def test_same_car_label_in_different_locations_is_not_duplicate(self):
        tickets=load_fixture()
        self.assertFalse(any(code=='POSSIBLE_DUPLICATE' for f in intake(tickets) for code,_ in f['flags']))
        flags={f['ticket_id']:{c for c,_ in f['flags']} for f in intake(tickets)}
        self.assertIn('HAZARD_REVIEW_REQUIRED',flags['ED-002'])
        self.assertIn('INVALID_TICKET_DATA',flags['ED-011'])
    def test_same_building_borough_asset_and_time_flags_both(self):
        first=load_fixture()[0]
        second=replace(first,ticket_id='ED-OTHER',created_at=first.created_at+timedelta(hours=1))
        self.assertEqual(len(intake([first,second])),2)
        self.assertFalse(intake([first,replace(second,sector='Other borough')]))
        self.assertFalse(intake([first,replace(second,created_at=first.created_at+timedelta(hours=25))]))
