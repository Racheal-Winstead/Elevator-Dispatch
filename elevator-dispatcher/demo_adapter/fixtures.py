"""Synthetic data only; does not implement Deshawn's ingest or triage modules."""
from datetime import timedelta
from models import Ticket
from roster import demo_day, BOROUGHS

def load_fixture(count=12):
    day=demo_day()
    tickets=[]
    for i in range(count):
        tickets.append(Ticket(f'ED-{i+1:03}',f'SEED-{i+1:03}',f'Demo Court {i%4+1}',
            ('Brooklyn','Queens','Manhattan','Bronx','Manhattan','Staten Island')[i%6],'DEPOT-A',f'CAR-{i%6+1}',
            'Caller reports stuck car — confirmation required' if i==1 else 'Synthetic elevator service request',
            day-timedelta(hours=count-i),1 if i==0 else 2+i%3,hazard_review=i==1,critical=i==0))
    if count>=12:
        from dataclasses import replace
        tickets[10]=replace(tickets[10],building='')
        tickets[11]=replace(tickets[11],sector='Bronx',critical=True)
    return tickets
