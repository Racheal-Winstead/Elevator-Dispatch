"""Adapt Deshawn's advisory/messaging functions to shared local records.

Upstream files stay unchanged. Imports are scoped to a private engine instance;
no sys.modules replacement, network transport, or source-switch app is used.
"""
import builtins
from datetime import timedelta
import hashlib
import json
from types import ModuleType
from pathlib import Path
import pandas as pd
from integrations.deshawn_adapter import load_engine, ticket_to_engine, staff_to_engine, commitments_to_engine, ROOT
from validators import eligible, ticket_errors, validate
from time_windows import utc, window, booked

def feature_module(name,engine):
    data=json.loads((ROOT/'FEATURE_SOURCES.json').read_text())[name+'.py']
    path=ROOT/('deshawn_'+name+'.py')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=data['sha256']: raise ValueError('UPSTREAM_FEATURE_CHECKSUM_MISMATCH')
    module=ModuleType('_private_'+name)
    original=builtins.__import__
    def scoped_import(name,*args,**kwargs):
        return engine if name=='engine' else original(name,*args,**kwargs)
    module.__dict__['__builtins__']={**vars(builtins),'__import__':scoped_import}
    exec(compile(path.read_text(),str(path),'exec'),module.__dict__)
    return module

def context(ticket,roster,assignments,clock):
    clock=utc(clock)
    assignment=next((a for a in assignments if a['ticket_id']==ticket.ticket_id),None)
    start,end=window(assignment['start'],assignment['end']) if assignment else (clock,clock+timedelta(minutes=1))
    engine=load_engine(); engine.DEMO_NOW=pd.Timestamp(clock.replace(tzinfo=None))
    engine.SLOTS={'SHARED':(start.strftime('%H:%M'),end.strftime('%H:%M'))}
    row=ticket_to_engine(ticket)
    row['triage']=2 if ticket.critical else 3
    board=commitments_to_engine(assignments,roster,start,end,'SHARED')
    people=[staff_to_engine(p,start,end) for p in roster]
    return engine,row,board,people,start,end,assignment

def recipient_check(ticket,person,roster,assignments,clock):
    clock=utc(clock)
    if not person.active or person.attendance!='PRESENT': return ('MESSAGE_BLOCKED_OFF_DUTY','Recipient is not confirmed present and active.',False)
    try:
        if not utc(person.shift_start)<=clock<utc(person.shift_end): return ('MESSAGE_BLOCKED_OFF_DUTY','Recipient is outside the current simulated shift.',False)
    except ValueError: return ('MESSAGE_BLOCKED_OFF_DUTY','Recipient shift is invalid.',False)
    engine,row,board,people,start,end,assignment=context(ticket,roster,assignments,clock)
    messages=feature_module('messaging',engine)
    # Set DEMO_NOW to the SAME clock used by the final send. This compensates
    # for the reviewed upstream send_message call that references this global.
    return messages.check_recipient(next(p for p in people if p['tech_id']==person.technician_id),ticket.ticket_id,board,pd.Timestamp(clock))

def send_simulated(ticket,person,roster,assignments,clock,actor,body,urgent=False,confirm_conflict=False):
    if not body.strip() or not actor.strip(): raise ValueError('Sender and message text are required')
    block=recipient_check(ticket,person,roster,assignments,clock)
    if block and not(block[2] and urgent and confirm_conflict): raise ValueError(block[0]+': '+block[1])
    engine,row,board,people,start,end,assignment=context(ticket,roster,assignments,clock)
    module=feature_module('messaging',engine)
    msg,blocked=module.send_message(ticket_id=ticket.ticket_id,tech=next(p for p in people if p['tech_id']==person.technician_id),body=body,urgent=urgent,sender=actor,assignments=board,messages=[],now=pd.Timestamp(utc(clock)),confirm_conflict=confirm_conflict)
    if blocked: raise ValueError(blocked[0])
    for key in ('sent_at','responded_at'):
        if msg.get(key) is not None: msg[key]=utc(msg[key]).isoformat()
    msg['assignment_group_id']=assignment.get('atomic_group_id','') if assignment else ''
    return msg

def draft_message(ticket,roster,assignments,clock,urgent=False):
    engine,row,board,people,start,end,assignment=context(ticket,roster,assignments,clock)
    names={p.technician_id:p.alias for p in roster}
    crew={p.role:names[p.technician_id] for p in roster if assignment and p.technician_id in assignment['crew']}
    return 'SIMULATED DEMO — '+feature_module('agents',engine).notification_draft(row,'SHARED',crew,urgent)

def reply_message(message,response,clock,reason):
    engine=load_engine(); module=feature_module('messaging',engine)
    result=dict(message)
    module.respond(result,response,pd.Timestamp(utc(clock)),reason)
    result['responded_at']=utc(result['responded_at']).isoformat()
    return result

def overdue(messages,clock):
    engine=load_engine(); module=feature_module('messaging',engine)
    converted=[{**m,'sent_at':pd.Timestamp(m['sent_at'])} for m in messages if not m.get('cancelled')]
    return [m['message_id'] for m in module.no_ack(converted,pd.Timestamp(utc(clock)))]

def availability(ticket,roster,rule,start,end,assignments):
    rows=[]
    for p in roster:
        errors=eligible(p,ticket,start,end,rule)
        if p.role not in rule.roles: errors.append('ROLE_NOT_REQUIRED')
        try:
            if booked(p.technician_id,start,end,assignments): errors.append('MANUAL_CONFLICT')
        except ValueError: errors.append('INVALID_TIME_WINDOW')
        rows.append({'ID':p.technician_id,'Person':p.alias,'Role':p.role,'Readiness':'Excluded' if errors else 'Individual checks passed','Reasons':', '.join(sorted(set(errors)))})
    return rows

def intake(tickets):
    rows=[]
    for t in tickets:
        errors=ticket_errors(t)
        related=[x.ticket_id for x in tickets if x.ticket_id!=t.ticket_id and t.asset and x.asset==t.asset and abs(utc(x.created_at)-utc(t.created_at))<=timedelta(hours=24)]
        rows.append({'ticket_id':t.ticket_id,'data_status':'INVALID_TICKET_DATA' if 'INVALID_TICKET_DATA' in errors else 'OK','issues':', '.join(errors),'possible_dup_of':', '.join(related),'hazard_keyword':t.hazard_review})
    return feature_module('agents',load_engine()).intake_agent(rows)

def explain(code):
    value=feature_module('agents',load_engine()).exception_explainer(code)
    overrides={'CREW_UNAVAILABLE':'Keep all required crew roles together; choose another complete crew/window or seek supervisor review.',
               'NO_CAPACITY':'Review available capacity with the supervisor; no existing assignment is displaced automatically.',
               'QUALIFICATION_UNVERIFIED':'Confirm eligibility from an authoritative source; do not bypass the hold.',
               'QUALIFICATION_EXPIRED':'Choose a person whose verified qualification covers the entire window.',
               'TECH_INACTIVE':'Choose an active eligible person.',
               'INVALID_TIME_WINDOW':'Correct the timezone-aware window and rerun checks.'}
    if code in overrides: value['next_action']=overrides[code]
    return value

def activity_summary(events):
    kinds={'STATUS':'STATUS_CHANGE','REMOVE':'UNASSIGN','MESSAGE_REPLY':'MESSAGE_REPLY'}
    rows=[{**e,'event_type':kinds.get(e['event_type'],e['event_type']),'entity':e['entity_id']} for e in events]
    # The upstream summary treats historical BLOCKED/NO_ACK entries as current.
    # Use it only for historical counters; current follow-up is derived separately.
    safe=[e for e in rows if e['event_type'] not in ('NO_ACK','STATUS_CHANGE') or (e['event_type']=='STATUS_CHANGE' and e['new_value']!='BLOCKED')]
    return feature_module('agents',load_engine()).handover_agent(safe)
