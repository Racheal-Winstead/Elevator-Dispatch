"""Communication and advice views sharing the console's Store and models."""
import pandas as pd
import streamlit as st
from models import STATUSES
from display_time import ny_time,ny_window
from integrations import feature_bridge as bridge
from state.audit import report
from validators import validate

def render(store,tickets,roster,rules,windows,actor,proposals,exceptions):
    st.markdown('<div class="section-label">SHARED WORKFLOW / MESSAGES & ADVICE</div>',unsafe_allow_html=True)
    st.subheader('One work order. One shared history.')
    st.info('SIMULATED ONLY · Messages stay in this local app. No SMS, email or field delivery.')
    st.caption('Adapted from Deshawn’s pinned messaging and advisory functions. Deterministic advice; no LLM calls or autonomous assignments.')
    if st.session_state.get('communication_success'): st.success(st.session_state.pop('communication_success'))
    clock=store.clock()
    st.caption('Shared simulated clock: '+ny_time(clock)+' · 15-minute acknowledgement threshold is a demo setting.')
    if st.button('Simulate 15 minutes passing',key='advance_shared_clock'):
        try: store.advance_clock(15,actor); st.rerun()
        except ValueError as e: st.error(str(e))
    selected=st.selectbox('Work order to message',[t.ticket_id for t in tickets],key='message_ticket')
    ticket=next(t for t in tickets if t.ticket_id==selected)
    assignments=store.assignments()
    assignment=next((a for a in assignments if a['ticket_id']==selected),None)
    st.write(f'**{selected} · {ticket.building or "Location needs review"} · {ticket.sector}**')
    st.write('**Saved crew:** '+(', '.join(assignment['crew']) if assignment else 'No committed crew'))
    if assignment: st.caption('Saved assignment window: '+ny_window(pd.Timestamp(assignment['start']),pd.Timestamp(assignment['end'])))
    late=set(bridge.overdue(store.messages(),clock))
    for m in store.messages(selected):
        if m['message_id'] in late: st.warning(f'NO_ACK · {m["message_id"]} · {m["recipient"]} needs dispatcher follow-up.')
    with st.expander('Availability advice — current saved board',expanded=False):
        start,end=(pd.Timestamp(assignment['start']),pd.Timestamp(assignment['end'])) if assignment else windows[0]
        st.dataframe(pd.DataFrame(bridge.availability(ticket,roster,rules[ticket.work_type],start,end,assignments)),hide_index=True,width='stretch')
        st.caption('Individual availability does not authorize a partial crew or bypass a ticket review hold. Messaging also checks whether the person is on duty at the current simulated time.')
    proposal=next((p for p in proposals if p.ticket_id==selected),None)
    if proposal:
        errors=validate(proposal,ticket,roster,rules[ticket.work_type],assignments)
        st.caption('Proposal conflict check: '+(', '.join(errors) if errors else 'passes the shared validator; still requires confirmation on Dispatch plan'))
    crew_ids=assignment['crew'] if assignment else []
    recipients=sorted(roster,key=lambda p:(p.technician_id not in crew_ids,p.technician_id))
    recipient_id=st.selectbox('Recipient',[p.technician_id for p in recipients],format_func=lambda ident:next(p.alias+' · '+p.technician_id for p in roster if p.technician_id==ident),key='message_recipient_'+selected)
    person=next(p for p in roster if p.technician_id==recipient_id)
    block=bridge.recipient_check(ticket,person,roster,assignments,clock)
    if block: st.warning(block[0]+' · '+block[1])
    with st.form('send_message_'+selected):
        body=st.text_area('Review message draft',value=bridge.draft_message(ticket,roster,assignments,clock),key='message_body_'+selected)
        urgent=st.checkbox('Urgent simulated message',key='message_urgent_'+selected)
        confirm=st.checkbox('I reviewed any booking conflict and approve an urgent message only; do not move the assignment',key='message_conflict_'+selected)
        if st.form_submit_button('Save simulated message',type='primary'):
            try:
                message=store.send(ticket,person,roster,actor,body,urgent,confirm)
                st.session_state.communication_success='Saved '+message['message_id']+' to the shared work-order history. No external message sent.'
                st.rerun()
            except ValueError as e: st.error('Message not saved: '+str(e))
    st.markdown('#### Shared outbox and simulated replies')
    messages=store.messages(selected)
    if not messages: st.caption('No messages saved for this work order yet.')
    for message in reversed(messages):
        mid=message['message_id']
        st.write(f'**{mid} → {message["recipient"]}** · {message["response"] or "Awaiting reply"}')
        st.caption(ny_time(message['sent_at'])+' · SIMULATED')
        with st.expander('Message details · '+mid): st.write(message['body'])
        if message['response']:
            st.caption('Recorded reply: '+message['response']+' · '+(message.get('response_reason') or 'No additional reason'))
            continue
        with st.form('reply_'+mid):
            response=st.selectbox('Simulated recipient reply',['ACKNOWLEDGED','CANNOT_RESPOND','DECLINED'],key='reply_type_'+mid)
            reason=st.text_input('Reply reason (required for Cannot respond)',key='reply_reason_'+mid)
            apply=st.checkbox('Apply this reply to shared work progress after my review',key='reply_apply_'+mid)
            st.caption('Acknowledged can mark the current assigned work ACKNOWLEDGED; Cannot respond or Declined can mark it BLOCKED. An old/reassigned crew reply cannot change current progress.')
            if st.form_submit_button('Record simulated reply'):
                try:
                    store.reply(mid,response,actor,reason,apply)
                    st.session_state.communication_success='Reply saved to shared history'+(' and work progress.' if apply else '. Progress was not changed.')
                    st.rerun()
                except ValueError as e: st.error('Reply not saved: '+str(e))
    with st.expander('Intake advice — selected work order',expanded=True):
        findings=bridge.intake(tickets)
        finding=next((f for f in findings if f['ticket_id']==selected),None)
        st.markdown('#### Intake review · '+selected)
        if finding:
            for code,detail in finding['flags']:
                st.warning(code.replace('_',' ').title()+' · '+detail)
                st.write('**Next human action:** '+bridge.explain(code)['next_action'])
        else:
            st.success('No intake flags found for this record.')
            st.caption('Required intake fields pass; no matching elevator record was found at the same building and borough within 24 hours. Crew eligibility is checked separately.')
        current=store.progress().get(selected,{})
        status=current.get('status','UNASSIGNED')
        st.write('**Saved workflow status:** '+status.replace('_',' ').title())
        if current.get('next_action'): st.write('**Recorded next action:** '+current['next_action'])
        elif status=='CLOSED': st.write('**Next workflow step:** Review the completed history and report.')
        elif status=='RESTORED': st.write('**Next workflow step:** Review the supporting report before closing the record.')
        elif status=='BLOCKED': st.write('**Next workflow step:** Review the recorded blocker and responsible owner before progressing the job.')
        elif status in ('EN_ROUTE','ON_SITE','DIAGNOSING','REPAIRING'): st.write('**Next workflow step:** Record the next reported field update; verify the supporting report before marking service restored.')
        elif status=='ACKNOWLEDGED': st.write('**Next workflow step:** Record the crew’s reported progress when available.')
        elif assignment: st.write('**Next workflow step:** Review this crew’s message and acknowledgement before recording field progress.')
        elif finding: st.write('**Next workflow step:** Review these intake flags before attempting assignment.')
        else: st.write('**Next workflow step:** Review readiness, then confirm a complete crew on Dispatch plan.')
        st.caption('Rule-based advice from the current records. It does not confirm emergencies, merge complaints, clear holds or change assignments.')
        with st.expander('All intake findings'):
            if findings:
                st.dataframe(pd.DataFrame([{'Ticket':f['ticket_id'],'Flags':'; '.join(c+': '+detail for c,detail in f['flags'])} for f in findings]),hide_index=True,width='stretch')
            else: st.caption('No intake flags found across the current source records.')
    with st.expander('Exception explanations — same scheduling results'):
        codes=sorted({code for values in exceptions.values() for code in values} | {'NO_ACK','CREW_UNAVAILABLE','ATTENDANCE_UNKNOWN'})
        code=st.selectbox('Explain reason code',codes,key='shared_explain_code')
        advice=bridge.explain(code)
        st.write('**Meaning:** '+advice['plain']); st.write('**Next human action:** '+advice['next_action'])

def handover_draft(store,tickets):
    rows=[r for r in report(tickets,store) if r['status']!='CLOSED']
    lines=['CURRENT OPEN WORK — draft for dispatcher review']
    for r in rows:
        lines.append(f'{r["ticket_id"]}: {r["status"]}; crew {r["crew"] or "unassigned"}; owner {r["owner"]}; next: {r["next_action"]}; reply: {r["last_reply"] or "none"}; {r["message_follow_up"]}')
    lines+=['','HISTORICAL ACTIVITY COUNTS — not current outstanding work',bridge.activity_summary(store.history())]
    return '\n'.join(lines)
