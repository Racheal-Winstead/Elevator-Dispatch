"""Replaceable fixture adapter, NOT Deshawn's production engine."""
from itertools import product
from models import Proposal
from validators import validate, ticket_errors

def recommend(tickets,roster,rules,windows,assignments):
    proposals=[]; exceptions={}; shadow=list(assignments)
    for t in sorted(tickets,key=lambda t:(not t.critical,t.priority,t.created_at,t.ticket_id)):
        if any(a['ticket_id']==t.ticket_id for a in shadow): continue
        errors=ticket_errors(t)
        rule=rules.get(t.work_type)
        if not rule: errors.append('UNKNOWN_WORK_TYPE')
        if errors:
            exceptions[t.ticket_id]=errors; continue
        found=None; reasons=set()
        groups=[[p.technician_id for p in sorted(roster,key=lambda p:p.technician_id) if p.role==r] for r in rule.roles]
        for start,end in windows:
            for crew in product(*groups):
                proposal=Proposal(t.ticket_id,crew,start,end)
                failures=validate(proposal,t,roster,rule,shadow)
                if not failures: found=proposal; break
                reasons.update(failures)
            if found: break
        if found:
            proposals.append(found)
            shadow.append({'ticket_id':t.ticket_id,'crew':list(found.crew),'start':found.start.isoformat(),'end':found.end.isoformat()})
        else: exceptions[t.ticket_id]=sorted(reasons or {'NO_QUALIFIED_CREW'})
    return proposals,exceptions
