"""Joint hard constraints shared by recommendation, readiness and commit paths."""
from collections import Counter
from models import RULE_VERSION
from time_windows import utc, window, overlaps

def ticket_errors(t):
    errors=[]
    if not t.ticket_id or not t.source_record_id or not t.building or not t.sector or not t.depot:
        errors.append('INVALID_TICKET_DATA')
    try: utc(t.created_at)
    except ValueError: errors.append('INVALID_TICKET_DATA')
    if t.priority not in (1,2,3,4,5): errors.append('UNKNOWN_PRIORITY')
    if t.hazard_review: errors.append('HAZARD_REVIEW_REQUIRED')
    return sorted(set(errors))

def eligible(p,t,start,end,rule):
    errors=[]
    if not p.active: errors.append('TECH_INACTIVE')
    if p.attendance!='PRESENT': errors.append('ATTENDANCE_UNKNOWN' if p.attendance=='UNKNOWN' else 'TECH_'+p.attendance)
    try:
        start,end=window(start,end); shift_start,shift_end=window(p.shift_start,p.shift_end)
        if not (shift_start<=start and end<=shift_end): errors.append('OFF_SHIFT')
        if p.certification_expiry and utc(p.certification_expiry)<end: errors.append('QUALIFICATION_EXPIRED')
    except ValueError: errors.append('INVALID_TIME_WINDOW')
    if t.sector not in p.sectors or t.depot not in p.depots: errors.append('SECTOR_OR_DEPOT_MISMATCH')
    if not set(rule.qualifications)<=set(p.qualifications): errors.append('NO_QUALIFIED_CREW')
    if p.certification_status not in ('DEMO_CONFIGURED','VERIFIED'): errors.append('QUALIFICATION_UNVERIFIED')
    return sorted(set(errors))

def validate(proposal,t,roster,rule,assignments,mode='DEMO_SEED'):
    errors=ticket_errors(t)
    if mode!='DEMO_SEED': errors.append('REAL_WORLD_ELIGIBILITY_UNVERIFIED')
    if proposal.ticket_id!=t.ticket_id: errors.append('TICKET_MISMATCH')
    if proposal.rule_version!=RULE_VERSION: errors.append('STALE_RULE_VERSION')
    try: window(proposal.start,proposal.end)
    except ValueError: errors.append('INVALID_TIME_WINDOW')
    people={p.technician_id:p for p in roster}
    crew=[people[c] for c in proposal.crew if c in people]
    if len(crew)!=len(proposal.crew) or len(set(proposal.crew))!=len(proposal.crew): errors.append('INVALID_CREW')
    if Counter(p.role for p in crew)!=Counter(rule.roles): errors.append('CREW_UNAVAILABLE')
    for p in crew: errors.extend(eligible(p,t,proposal.start,proposal.end,rule))
    for a in assignments:
        if a['ticket_id']==t.ticket_id: errors.append('ALREADY_ASSIGNED')
        try:
            if overlaps(proposal.start,proposal.end,a['start'],a['end']) and set(proposal.crew)&set(a['crew']): errors.append('MANUAL_CONFLICT')
        except (ValueError,KeyError,TypeError): errors.append('INVALID_TIME_WINDOW')
    return sorted(set(errors))
