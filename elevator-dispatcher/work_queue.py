"""Racheal's queue presentation helpers. No scheduling or source-priority changes."""
from validators import ticket_errors
from display_time import ny_time

def demo_work_order(ticket):
    # Fictional numeric presentation identifier. Internal stable IDs remain unchanged.
    suffix=ticket.ticket_id.removeprefix('ED-')
    return str(900000000+int(suffix)) if suffix.isdigit() else ticket.ticket_id

def queue_rows(tickets,progress,borough='ALL',quality='ALL',status='ALL',search=''):
    rows=[]
    for t in tickets:
        issues=ticket_errors(t); current=progress.get(t.ticket_id,{}).get('status','UNASSIGNED')
        if borough!='ALL' and t.sector!=borough: continue
        if quality=='NEEDS_REVIEW' and not issues: continue
        if quality=='READY' and issues: continue
        if status!='ALL' and current!=status: continue
        text=f'{demo_work_order(t)} {t.ticket_id} {t.building} {t.sector} {t.asset} {t.description}'.casefold()
        if search.strip().casefold() not in text: continue
        rows.append({'Work order #':demo_work_order(t),'Building':t.building or 'MISSING — review required','Borough':t.sector,'Elevator':t.asset,'Status':current,'Source priority':t.priority,'Reported (New York)':ny_time(t.created_at),'Data / review checks':', '.join(issues) or 'Ready for crew checks','Reported problem':t.description,'Internal ID':t.ticket_id})
    return rows
