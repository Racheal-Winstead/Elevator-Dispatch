"""Racheal's synthetic roster and configurable crew composition."""
from datetime import datetime, timedelta, timezone
from models import Technician, CrewRule

BOROUGHS = ('Manhattan', 'Bronx', 'Queens', 'Brooklyn', 'Staten Island')

ATTENDANCE = ('PRESENT','ABSENT','UNKNOWN','OFF_SHIFT','UNAVAILABLE')
RULES = {'CORRECTIVE': CrewRule(), 'INSPECTION': CrewRule(('MECHANIC',))}

def demo_day():
    return datetime.now(timezone.utc).replace(hour=13, minute=0, second=0, microsecond=0)

def slots(day=None):
    day = day or demo_day()
    return [(day+timedelta(hours=i*2),day+timedelta(hours=i*2+2)) for i in range(4)]

def demo_roster(day=None):
    day = day or demo_day()
    people=[]
    for i in range(10):
        people.append(Technician(f'T{i+1:02}',f'Demo {"Mechanic" if i%2==0 else "Helper"} {i+1:02}',
            'MECHANIC' if i%2==0 else 'HELPER',
            {3:'ABSENT',5:'UNKNOWN',7:'UNAVAILABLE'}.get(i,'PRESENT'),
            BOROUGHS if i==9 else (BOROUGHS[i//2],),
            ('DEPOT-A',),day,day+timedelta(hours=8)))
    return people
