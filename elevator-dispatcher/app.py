"""Racheal Winstead • Dispatcher console • local synthetic demonstration."""
from pathlib import Path
import os
from dataclasses import asdict, replace
from datetime import datetime, timezone
from time import perf_counter
from html import escape
import pandas as pd
import streamlit as st
from models import Proposal, STATUSES, RULE_VERSION
from roster import demo_roster, slots, RULES, ATTENDANCE
from validators import ticket_errors, eligible, validate
from work_queue import demo_work_order, queue_rows
from display_time import ny_time, ny_window, local_rows
from demo_adapter.fixtures import load_fixture
from integrations.deshawn_adapter import recommend, ENGINE_COMMIT
from time_windows import booked
from state.audit import Store, now, report, csv_export

st.set_page_config(page_title='Elevator Dispatcher | Workbench',page_icon='↕',layout='wide')
st.markdown("""<style>
:root {--navy:#142238;--pink:#a52b68;--line:#e6e7ed}
.stApp{background:#f7f7fa;color:#19283d} .block-container{max-width:1500px;padding-top:2rem;padding-bottom:3rem}
[data-testid="stSidebar"]{background:#142238;border-right:1px solid #2d3c52}
[data-testid="stSidebar"] :is(h1,h2,h3,p,label,small){color:#f4eaf0}
[data-testid="stSidebar"] input{color:#19283d}
[data-testid="stSidebar"] button p{color:#19283d!important}
h1,h2,h3{letter-spacing:-.035em} h1{font-weight:800}
div[data-testid="stMetric"]{background:white;border:1px solid #e6e7ed;border-radius:14px;padding:20px;border-top:3px solid #db85ad}
.hero{background:linear-gradient(115deg,#142238,#23354d);color:white;padding:32px 36px;border-radius:18px;margin-bottom:20px;position:relative;overflow:hidden}
.hero:after{content:'↕';position:absolute;right:30px;top:-45px;font-size:190px;color:#ffffff08;font-weight:800}
.hero h1{color:#fff;font-size:40px;line-height:1.2;margin:12px 0}.hero p{color:#d1dbe6;margin:0;max-width:750px;line-height:1.7}
.eyebrow{font-size:11px;font-weight:700;letter-spacing:.17em;color:#efafcd}
.hero-badge{display:inline-block;font-size:10px;letter-spacing:.1em;background:#f9dce9;color:#7e204e;padding:5px 10px;border-radius:30px;margin-bottom:10px}
.stButton button,.stDownloadButton button{border-radius:9px}.stButton button[kind="primary"]{background:#a52b68;border-color:#a52b68}
[data-baseweb="tab-list"]{gap:14px;border-bottom:1px solid #e6e7ed;padding-bottom:8px}
[data-baseweb="tab"]{font-size:13px;padding:12px 14px!important}
[data-baseweb="tab"][aria-selected="true"]{color:#a52b68!important;background:#fbeaf2;border-radius:8px}
[data-baseweb="tab-highlight"]{background:#a52b68}
.section-label{font-size:11px;color:#a52b68;letter-spacing:.15em;font-weight:700;margin:24px 0 6px}
.ticket-context{background:white;border:1px solid #e6e7ed;border-left:4px solid #b7487f;padding:18px 22px;border-radius:10px;margin:12px 0 20px}
.ticket-context strong{display:block;font-size:17px;margin:5px 0}.ticket-context p{color:#657185;font-size:13px;margin:4px 0}.ticket-context small{color:#a52b68;font-weight:700;letter-spacing:.04em}
.crew-card{background:white;border:1px solid #e6e7ed;border-radius:13px;padding:20px;margin-bottom:18px;min-height:270px;border-top:3px solid #e3b4cb}
.crew-card.blocked{border-top-color:#c5cbd4}.crew-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.crew-avatar{width:40px;height:40px;border-radius:10px;background:#f9e5ef;color:#91305f;display:grid;place-items:center;font-size:12px;font-weight:800}
.crew-status{font-size:10px;font-weight:700;padding:5px 9px;border-radius:20px;background:#e6f4ed;color:#246047}.crew-status.blocked{background:#f1f2f5;color:#5d6677}
.crew-card h3{font-size:17px;margin:0 0 3px}.crew-role{font-size:10px;letter-spacing:.12em;font-weight:700;color:#a52b68;margin-bottom:16px}
.crew-detail{font-size:12px;line-height:1.9;color:#617083}.crew-reason{margin-top:13px;padding-top:11px;border-top:1px solid #eceef3;font-size:11px;color:#46566d;line-height:1.6}
.crew-legend{font-size:12px;color:#66768a;margin:10px 0 18px}.crew-legend b{color:#29384e}
@media(max-width:700px){.hero{padding:24px}.hero h1{font-size:29px}.block-container{padding:1rem}.crew-card{min-height:0}}
</style>""",unsafe_allow_html=True)
ROOT=Path(__file__).parent
st.session_state.store=Store(os.environ.get('WORKBENCH_DB',str(ROOT/'workbench.sqlite3')))
if 'tickets' not in st.session_state or st.session_state.get('roster_version') != RULE_VERSION:
    st.session_state.roster_version=RULE_VERSION
    st.session_state.tickets=load_fixture()
    st.session_state.roster=demo_roster()
    st.session_state.refreshed=now()
    st.session_state.store.event('IMPORT','seed','Demo dispatcher',None,{'count':12,'mode':'DEMO_SEED'},'Synthetic fixture loaded')
store=st.session_state.store; tickets=st.session_state.tickets; roster=st.session_state.roster
with st.sidebar:
    st.title('↕ Dispatch\nCommand Desk')
    st.caption('Racheal Winstead • Product Operations & QA')
    actor=st.text_input('Dispatcher name / demo alias','Demo dispatcher')
    st.divider()
    st.markdown('**SOURCE MODE**\n\nDEMO SEED')
    st.caption('Synthetic work orders and personnel. Local single-user demonstration.')
    st.caption('Maximo / REMS / emergency dispatch: not connected.')
    st.caption(f'Policy {RULE_VERSION} • operations validation pending')
    st.caption(f'Scheduler: Deshawn pinned engine {ENGINE_COMMIT[:7]} via local data adapter. SQLite remains local.')
    if st.button('Refresh synthetic source'):
        st.session_state.refreshed=now()
        store.event('REFRESH','seed',actor,None,{'count':len(tickets)},'Re-read unchanged synthetic source; local state retained')
        st.rerun()
    st.caption('Monday milestone: date and time awaiting team confirmation.')

st.markdown('<div class="hero"><span class="hero-badge">SYNTHETIC DEMONSTRATION · NOT LIVE DISPATCH</span><div class="eyebrow">ELEVATOR SERVICES / DISPATCH COMMAND DESK</div><h1>The right crew.<br>The next clear move.</h1><p>A decision workspace for the people keeping service moving. Check readiness, understand the exceptions, and carry every next action forward.</p></div>',unsafe_allow_html=True)
st.info('DEMO SEED · Qualification and crew rules are demo-configured. External commitments are unknown; only this local board is checked.')
st.caption(f'Source generated: {ny_time(tickets[0].created_at)} · Last refresh: {ny_time(st.session_state.refreshed)} · Fetch: local fixture (no network) · {len(tickets)} records · Fallback: not active')
board=store.assignments(); assigned={a['ticket_id'] for a in board}; invalid=[t for t in tickets if 'INVALID_TICKET_DATA' in ticket_errors(t)]
valid=[t for t in tickets if not ticket_errors(t)]
start=perf_counter(); proposals,exceptions=recommend(tickets,roster,RULES,slots(),board); compute=perf_counter()-start
c1,c2,c3,c4=st.columns(4)
c1.metric('Received',len(tickets)); c2.metric('Committed crews',len(board)); c3.metric('Needs attention',len(exceptions)); c4.metric('Adapter compute',f'{compute*1000:.1f} ms')
st.caption(f'Reconciliation: {len(board)} assigned + {len(tickets)-len(board)-len(invalid)} unassigned non-invalid + {len(invalid)} invalid = {len(tickets)} received. Preview: {len(proposals)} recommendations; these are not committed assignments.')
urgent=[t for t in tickets if (t.critical or t.hazard_review) and t.ticket_id not in assigned]
if urgent:
    st.warning('HUMAN REVIEW · '+', '.join(t.ticket_id for t in urgent)+' — review reported hazard / critical impact and follow the applicable approved procedure. No automatic emergency declaration or preemption.')
def open_readiness(ticket_id):
    st.session_state.readiness_ticket=ticket_id
    st.session_state.workbench_view='01  Crew readiness'
def open_progress(ticket_id):
    st.session_state.progress_ticket=ticket_id
    st.session_state.workbench_view='04  Progress & exceptions'
def open_dispatch_plan(ticket_id):
    st.session_state.plan_ticket=ticket_id
    st.session_state.workbench_view='03  Dispatch plan'
crewtab,queue,plan,progress,export=st.tabs(['01  Crew readiness','02  Work queue','03  Dispatch plan','04  Progress & exceptions','05  Shift handover'],key='workbench_view',on_change='rerun')
with queue:
    st.markdown('<div class="section-label">RACHEAL’S WORKSTREAM / WORK-ORDER REVIEW</div>',unsafe_allow_html=True)
    st.subheader('Find the work. Understand the next step.')
    st.caption('Fictional numeric work-order numbers are for this demo only. These are not real NYCHA records. Displayed times use New York time (EST/EDT automatically). Stored/exported timestamps retain UTC.')
    a,b,c,d=st.columns([1,1,1,2])
    borough=a.selectbox('Borough filter',['ALL']+sorted({t.sector for t in tickets}))
    quality=b.selectbox('Review filter',['ALL','NEEDS_REVIEW','READY'])
    selected_status=c.selectbox('Work status',['ALL']+STATUSES)
    search=d.text_input('Search work order, building, borough, elevator or problem')
    rows=queue_rows(tickets,store.progress(),borough,quality,selected_status,search)
    st.caption(f'{len(rows)} of {len(tickets)} work orders match your filters. “Ready” means intake checks passed, not that a crew can be assigned.')
    if rows:
        st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
        ids=[r['Internal ID'] for r in rows]
        chosen=st.selectbox('Select a work order to inspect',ids,format_func=lambda tid:next(f'{demo_work_order(t)} · {t.building or "Location missing"} · {t.sector}' for t in tickets if t.ticket_id==tid),key='queue_ticket')
        t=next(t for t in tickets if t.ticket_id==chosen)
        issues=ticket_errors(t); state=store.progress().get(t.ticket_id,{})
        st.markdown(f'<div class="ticket-context"><small>WORK ORDER # {escape(demo_work_order(t))} · SYNTHETIC RECORD</small><strong>{escape(t.building or "Building missing — dispatcher review required")}</strong><p>{escape(t.description)}</p></div>',unsafe_allow_html=True)
        details,checks=st.columns([3,2])
        with details:
            st.markdown('#### Reported facts')
            st.write(f'**Borough:** {t.sector}  |  **Elevator:** {t.asset or "Not supplied"}')
            st.write(f'**Received:** {ny_time(t.created_at)}  |  **Source priority:** {t.priority}')
            st.write(f'**Work type:** {t.work_type}  |  **Current status:** {state.get("status","UNASSIGNED")}')
            st.write(f'**Source:** DEMO SEED / {t.source_record_id}  |  **Internal ID:** {t.ticket_id}')
            related=[demo_work_order(x) for x in tickets if x.asset and x.asset==t.asset and x.ticket_id!=t.ticket_id]
            if related: st.info('Other demo records reference this elevator: '+', '.join(related)+'. Possible related complaints, not confirmed duplicates. No records were merged.')
        with checks:
            st.markdown('#### Before assignment')
            if issues:
                for issue in issues:
                    message={'INVALID_TICKET_DATA':'Missing required work-order details. Confirm the building and other required fields.','HAZARD_REVIEW_REQUIRED':'Reported hazard language needs human confirmation. This is not an automatically confirmed emergency.','UNKNOWN_PRIORITY':'Priority is not recognized. Confirm its source before scheduling.'}.get(issue,issue)
                    st.warning(message)
                st.caption('Crew readiness may be inspected, but this ticket remains blocked from assignment until its review hold is resolved through the approved process.')
            else: st.success('Intake checks passed. Next, inspect complete-crew eligibility and availability.')
            st.markdown('**Demo interpretation — not source policy**')
            st.write('Human hazard review' if t.hazard_review else 'Critical service impact (synthetic flag)' if t.critical else 'Standard demo work')
            if state.get('next_action'): st.write('**Recorded next action:** '+state['next_action'])
        st.button('Check crew readiness →',type='primary',on_click=open_readiness,args=(chosen,),key='queue_to_crew')
    else:
        st.info('No work orders match. Clear the search or choose ALL in the filters to see more work. No records have been deleted.')
with crewtab:
    st.markdown('<div class="section-label">RACHEAL’S WORKSTREAM / ROSTER & READINESS</div>',unsafe_allow_html=True)
    st.subheader('Know who can take the next job.')
    st.caption('Choose a work order and time window. Readiness is checked against demo rules and this local board—not live staffing systems.')
    left,right=st.columns([2,1])
    selected=left.selectbox('Check crew for work order',[t.ticket_id for t in tickets],format_func=lambda tid:next(f'{demo_work_order(t)} · {t.building or "Location missing"}' for t in tickets if t.ticket_id==tid),key='readiness_ticket')
    windows=slots()
    window=right.selectbox('Assignment window (New York time)',range(len(windows)),format_func=lambda i:ny_window(*windows[i]),key='readiness_window')
    selected_ticket=next(t for t in tickets if t.ticket_id==selected)
    start_time,end_time=windows[window]
    rule=RULES.get(selected_ticket.work_type)
    st.markdown(f'<div class="ticket-context"><small>WORK ORDER # {escape(demo_work_order(selected_ticket))} · {escape(selected_ticket.sector)} · {escape(selected_ticket.depot)}</small><strong>{escape(selected_ticket.building or "Location requires review")}</strong><p>{escape(selected_ticket.description)}</p><p>Required demo crew: {escape(" + ".join(rule.roles) if rule else "Unknown work type")} · {ny_window(start_time,end_time)}</p></div>',unsafe_allow_html=True)
    reasons={}
    labels={'ATTENDANCE_UNKNOWN':'Attendance unknown — do not assume available','TECH_ABSENT':'Marked absent','TECH_UNAVAILABLE':'Marked unavailable','TECH_OFF_SHIFT':'Marked off shift','TECH_INACTIVE':'Inactive resource','OFF_SHIFT':'Outside recorded shift','SECTOR_OR_DEPOT_MISMATCH':'Not authorized for this borough / depot','NO_QUALIFIED_CREW':'Required demo qualification missing','QUALIFICATION_UNVERIFIED':'Qualification not verified under demo rules','QUALIFICATION_EXPIRED':'Qualification expires before work ends','MANUAL_CONFLICT':'Already assigned in this window','ROLE_NOT_REQUIRED':'Role not required for this work type','UNKNOWN_WORK_TYPE':'Crew requirements not configured'}
    for person in roster:
        errors=eligible(person,selected_ticket,start_time,end_time,rule) if rule else ['UNKNOWN_WORK_TYPE']
        if rule and person.role not in rule.roles: errors.append('ROLE_NOT_REQUIRED')
        try:
            if booked(person.technician_id,start_time,end_time,board): errors.append('MANUAL_CONFLICT')
        except ValueError: errors.append('INVALID_TIME_WINDOW')
        reasons[person.technician_id]=list(dict.fromkeys(errors))
    ready=[p for p in roster if not reasons[p.technician_id]]
    ticket_issues=ticket_errors(selected_ticket)
    if ticket_issues: st.warning('Ticket needs review before assignment: '+', '.join(ticket_issues)+'. Staff readiness does not override this hold.')
    st.markdown(f'<div class="crew-legend"><b>{len(ready)} pass individual demo checks</b> · {len(roster)-len(ready)} excluded · Complete crew and ticket validation still required before commitment.</div>',unsafe_allow_html=True)
    role_filter=st.radio('Show crew roles',['All staff','Mechanics','Helpers'],horizontal=True)
    visible=[p for p in roster if role_filter=='All staff' or p.role==('MECHANIC' if role_filter=='Mechanics' else 'HELPER')]
    columns=st.columns(3)
    for index,person in enumerate(visible):
        errors=reasons[person.technician_id]; blocked=bool(errors); css='blocked' if blocked else ''; badge='Excluded' if blocked else 'Demo checks passed'
        explanation=' · '.join(labels.get(e,e) for e in errors) if errors else 'Present · in shift · borough authorized · demo qualification passes'
        with columns[index%3]:
            st.markdown(f'<div class="crew-card {css}"><div class="crew-top"><span class="crew-avatar">{escape(person.technician_id)}</span><span class="crew-status {css}">{badge}</span></div><h3>{escape(person.alias)}</h3><div class="crew-role">{escape(person.role)}{" · FLOAT" if person.technician_id=="T10" else ""}</div><div class="crew-detail">Attendance: <b>{escape(person.attendance)}</b><br>Shift: {ny_window(person.shift_start,person.shift_end)}<br>Boroughs: {escape(", ".join(person.sectors))} · {escape(", ".join(person.depots))}<br>Qualification: {escape(person.certification_status)}</div><div class="crew-reason">{escape(explanation)}</div></div>',unsafe_allow_html=True)
    st.button('Review this work order’s dispatch plan →',on_click=open_dispatch_plan,args=(selected,),key='crew_to_plan')
    st.caption('10 fictional personnel. T10 is a demo-authorized float helper. A green readiness label is not a real-world qualification or authorization claim.')
    st.markdown('#### Roster records and attendance')
    st.dataframe(pd.DataFrame([{'ID':p.technician_id,'Alias':p.alias,'Role':p.role,'Attendance':p.attendance,'Active':p.active,'Boroughs':', '.join(p.sectors),'Depots':', '.join(p.depots),'Qualifications':', '.join(p.qualifications),'Verification':p.certification_status,'Shift (New York)':ny_window(p.shift_start,p.shift_end)} for p in roster]),hide_index=True,width='stretch')
    with st.form('attendance'):
        tech=st.selectbox('Technician',[p.technician_id for p in roster]); attendance=st.selectbox('Attendance state',ATTENDANCE)
        if st.form_submit_button('Record attendance'):
            if any(tech in a['crew'] for a in board): st.error('Remove or reassign existing commitments before changing attendance.')
            else:
                old=next(p for p in roster if p.technician_id==tech)
                store.event('ATTENDANCE',tech,actor,old.attendance,attendance,'Dispatcher demo roster update')
                st.session_state.roster=[replace(p,attendance=attendance) if p.technician_id==tech else p for p in roster]; st.rerun()
    st.markdown('#### Crew rules')
    st.caption('Illustrative rules for this demonstration—not verified NYCHA staffing policy.')
    for work_type, rule in RULES.items():
        role_counts={role:rule.roles.count(role) for role in dict.fromkeys(rule.roles)}
        crew_label=' + '.join(f'{count} {role.lower()}{"s" if count != 1 else ""}' for role,count in role_counts.items())
        st.write(f'**{work_type.replace("_", " ").title()} work:** {crew_label}.')
    st.write('**Before assignment:** all required crew members must pass attendance, shift, borough/depot authorization, qualification, and scheduling-conflict checks.')
    st.caption('“ELEVATOR_DEMO” is a fictional test qualification. It does not establish real-world certification or authorization.')
    with st.expander('Technical configuration — for builders'):
        st.json({k:{'required_roles':v.roles,'required_qualifications':v.qualifications,'rule_source':v.source} for k,v in RULES.items()})
        st.caption('Configuration lives in roster.py. Validate operational rules before any real-world use.')
with plan:
    st.markdown('<div class="section-label">RACHEAL’S WORKSTREAM / REVIEW & CONFIRM</div>',unsafe_allow_html=True)
    st.subheader('A proposal first. Your decision next.')
    st.caption('Deshawn’s pinned scheduling engine is connected through a local data adapter. Recommendations are previews, not assignments. Only the local demo board is checked; team merge and shared storage approval remain pending.')
    if st.session_state.get('dispatch_success'):
        st.success(st.session_state.pop('dispatch_success'))
    ticket_ids=[t.ticket_id for t in tickets]
    chosen=st.selectbox('Work order to plan',ticket_ids,format_func=lambda tid:next(f'{demo_work_order(t)} · {t.building or "Location missing"} · {t.sector}' for t in tickets if t.ticket_id==tid),key='plan_ticket')
    selected_order=next(t for t in tickets if t.ticket_id==chosen)
    proposal=next((item for item in proposals if item.ticket_id==chosen),None)
    existing=next((item for item in board if item['ticket_id']==chosen),None)
    st.markdown(f'<div class="ticket-context"><small>WORK ORDER # {escape(demo_work_order(selected_order))} · {escape(selected_order.sector)}</small><strong>{escape(selected_order.building or "Building requires review")}</strong><p>{escape(selected_order.description)}</p></div>',unsafe_allow_html=True)
    if existing:
        st.info('This work order already has a committed crew: '+', '.join(existing['crew'])+'. Use the manual reassignment section to propose a replacement; no duplicate assignment is created here.')
    elif proposal:
        crew_by_id={person.technician_id:person for person in roster}
        st.markdown('#### Proposed complete crew')
        crew_columns=st.columns(len(proposal.crew))
        for column,tid in zip(crew_columns,proposal.crew):
            person=crew_by_id[tid]
            with column:
                st.markdown(f'<div class="crew-card"><div class="crew-top"><span class="crew-avatar">{escape(tid)}</span><span class="crew-status">Proposed · not assigned</span></div><h3>{escape(person.alias)}</h3><div class="crew-role">{escape(person.role)}</div><div class="crew-detail">Attendance: {escape(person.attendance)}<br>Authorized boroughs: {escape(", ".join(person.sectors))}<br>Qualification: {escape(person.certification_status)}</div><div class="crew-reason">{ny_window(proposal.start,proposal.end)} · {ny_time(proposal.start).split(" · ")[0]}</div></div>',unsafe_allow_html=True)
        st.caption('The plan considers other pending recommendations. Its window or helper can differ from the individual-readiness screen, which checks only the committed board.')
        failures=validate(proposal,selected_order,roster,RULES[selected_order.work_type],board)
        if failures: st.error('Current checks failed: '+', '.join(failures))
        else: st.success('Complete-crew checks pass against the current demo board: roles, attendance, shift, configured qualifications, borough/depot authorization, and overlapping commitments.')
        st.write('**Why this proposal:** '+proposal.explanation)
        st.write('**What confirmation changes:** saves every required crew member together, marks the work ASSIGNED, and records the dispatcher, time and decision reason. Other assignments stay in place. No field notification or Maximo update is sent.')
        with st.form('confirm_dispatch_'+chosen):
            decision_reason=st.text_input('Assignment decision reason',value='Reviewed complete demo crew and time window',key='dispatch_reason_'+chosen)
            acknowledged=st.checkbox('I reviewed this complete crew and time window',key='dispatch_ack_'+chosen)
            commit_clicked=st.form_submit_button('Confirm complete crew assignment',type='primary',disabled=bool(failures))
            if commit_clicked:
                if not acknowledged: st.error('Review the proposal and check the confirmation box first. No assignment was saved.')
                elif not decision_reason.strip(): st.error('Enter a decision reason. No assignment was saved.')
                else:
                    try:
                        store.commit(proposal,selected_order,roster,RULES[selected_order.work_type],actor,decision_reason)
                        st.session_state.dispatch_success=f'Work order {demo_work_order(selected_order)} assigned to '+', '.join(proposal.crew)+'. Complete crew saved together; activity recorded. No external dispatch was sent.'
                        st.rerun()
                    except ValueError as error: st.error('Assignment rejected; prior schedule preserved: '+str(error))
    else:
        reasons=exceptions.get(chosen,['NO_CAPACITY'])
        st.warning('No complete crew recommendation for this work order: '+', '.join(reasons))
        st.write('**Next step:** review the work-order details or recorded availability. Use Progress & exceptions to record the responsible person and follow-up. Do not force a partial crew or override an unresolved hold.')
    st.button('Track this work order’s progress →',on_click=open_progress,args=(chosen,),key='plan_to_progress')
    with st.expander('All pending recommendations'):
        st.dataframe(pd.DataFrame([{'Work order #':demo_work_order(next(t for t in tickets if t.ticket_id==item.ticket_id)),'Proposed crew':', '.join(item.crew),'Start (New York)':ny_time(item.start),'End (New York)':ny_time(item.end)} for item in proposals]),hide_index=True,width='stretch')
    with st.expander('Manual assignment / reassignment — same validator'):
        with st.form('manual'):
            tid=st.selectbox('Work order',[t.ticket_id for t in tickets]); crew=st.multiselect('Crew IDs',[p.technician_id for p in roster])
            windows=slots(); slot=st.selectbox('Time window (New York time)',range(len(windows)),format_func=lambda i:ny_window(*windows[i]))
            reason=st.text_input('Decision reason'); replace_existing=st.checkbox('Replace this ticket’s existing complete crew')
            st.caption('Preview above: selected crew and time replace only this ticket when checked. No other ticket is displaced. Full validation runs on commit.')
            if st.form_submit_button('Validate and commit manual proposal'):
                try:
                    t=next(t for t in tickets if t.ticket_id==tid)
                    store.commit(Proposal(tid,tuple(crew),*windows[slot],scheduler_source='MANUAL'),t,roster,RULES[t.work_type],actor,reason,replace_existing); st.rerun()
                except ValueError as e: st.error(f'Assignment rejected; prior board preserved: {e}')
    st.markdown('**Committed schedule**')
    if board:
        st.dataframe(pd.DataFrame(local_rows(board)),hide_index=True,width='stretch')
        removal=st.selectbox('Remove complete assignment',[a['ticket_id'] for a in board])
        if st.button('Remove selected complete crew'):
            store.remove(removal,actor,'Dispatcher removed complete assignment'); st.rerun()
    else: st.info('EMPTY DEMO BOARD · No external commitments were imported.')
with progress:
    st.markdown('<div class="section-label">RACHEAL’S WORKSTREAM / FOLLOW-THROUGH</div>',unsafe_allow_html=True)
    st.subheader('Every update leaves a clear next step.')
    st.caption('Updates are entered by the dispatcher—not received from field devices. New York time is displayed; UTC is stored for a consistent history.')
    if st.session_state.get('progress_success'): st.success(st.session_state.pop('progress_success'))
    tid=st.selectbox('Work order to track',[t.ticket_id for t in tickets],format_func=lambda ident:next(f'{demo_work_order(t)} · {t.building or "Location missing"} · {t.sector}' for t in tickets if t.ticket_id==ident),key='progress_ticket')
    t=next(t for t in tickets if t.ticket_id==tid)
    current=store.progress().get(tid,{})
    assignment=next((a for a in board if a['ticket_id']==tid),None)
    status_now=current.get('status','UNASSIGNED')
    st.markdown(f'<div class="ticket-context"><small>WORK ORDER # {escape(demo_work_order(t))} · {escape(status_now)}</small><strong>{escape(t.building or "Building needs review")}</strong><p>{escape(t.description)}</p><p>Recorded crew: {escape(", ".join(assignment["crew"]) if assignment else "No committed crew")}</p></div>',unsafe_allow_html=True)
    overview,update=st.columns([1,2])
    with overview:
        st.markdown('#### Current follow-up')
        st.write('**Responsible owner:** '+current.get('owner','Not recorded'))
        st.write('**Last update:** '+ny_time(current.get('last_update')))
        st.write('**Next action:** '+current.get('next_action','Not recorded'))
        st.write('**Blocker:** '+(current.get('blocker') or 'None recorded'))
        if tid in exceptions: st.warning('Scheduling exception: '+', '.join(exceptions[tid]))
    with update:
        st.markdown('#### Record an update')
        available=[s for s in STATUSES if s!='UNASSIGNED'] if assignment else ['UNASSIGNED','BLOCKED']
        if assignment: st.caption('To mark UNASSIGNED, remove the complete crew on Dispatch plan. This keeps status and capacity consistent.')
        with st.form('progress_update_'+tid):
            status=st.selectbox('New status',available,index=available.index(status_now) if status_now in available else 0,key='new_status_'+tid)
            owner=st.text_input('Responsible person / team',value=current.get('owner',''),key='owner_'+tid)
            action=st.text_input('Next action',value=current.get('next_action',''),key='next_'+tid)
            blocker=st.text_input('Blocker / escalation details',value=current.get('blocker',''),key='blocker_'+tid)
            reason=st.text_input('Why are you recording this update?',key='update_reason_'+tid)
            st.caption('RESTORED means service was reported back. CLOSED is a separate recordkeeping decision; neither updates Maximo. No rigid status-transition policy is claimed for this demo.')
            confirm_final=st.checkbox('If marking Restored or Closed, I have checked the supporting report',key='final_ack_'+tid)
            if st.form_submit_button('Save progress update',type='primary'):
                if status in ('RESTORED','CLOSED') and not confirm_final: st.error('Confirm the supporting report before recording Restored or Closed. Nothing was saved.')
                else:
                    try:
                        store.status(tid,status,actor,action,blocker,reason,owner=owner)
                        st.session_state.progress_success='Progress saved with responsible owner, next action and dispatcher audit record.'
                        st.rerun()
                    except ValueError as error: st.error('Update not saved: '+str(error))
    st.markdown('#### Work-order activity')
    events=[e for e in store.history() if e['entity_id']==tid]
    if events:
        st.dataframe(pd.DataFrame([{'New York time':ny_time(e['timestamp']),'Event':e['event_type'],'Recorded by':e['actor'],'Reason':e['reason']} for e in events]),hide_index=True,width='stretch')
    else: st.info('No recorded activity for this work order yet. Its initial state comes from the synthetic dataset.')
    with st.expander('All scheduling exceptions'):
        st.dataframe(pd.DataFrame([{'Work order #':demo_work_order(next(t for t in tickets if t.ticket_id==ident)),'Reason codes':', '.join(codes)} for ident,codes in exceptions.items()]),hide_index=True,width='stretch')
    st.caption('Unassigned critical work and hazard-review flags require human action under the applicable approved procedure. This screen does not send an external escalation or enforce an unvalidated 90-minute timer.')
with export:
    st.subheader('Leave the next shift a usable record')
    rows=report(tickets,store)
    st.dataframe(pd.DataFrame(local_rows(rows)),hide_index=True,width='stretch')
    open_rows=[r for r in rows if r['status']!='CLOSED']
    for label,subset in [('Daily assignment',[r for r in rows if r['crew']]),('Open work',open_rows),('Unassigned exceptions',[r for r in rows if not r['crew']]),('Shift handover',open_rows)]:
        st.download_button(f'Download {label.lower()} CSV',csv_export(subset),file_name=label.lower().replace(' ','_')+'.csv',mime='text/csv')
    st.caption('Reporting window: current synthetic fixture and local board. “Dispatcher review” is an explicit queue owner awaiting named acknowledgement; it is not a confirmed external assignee. Notifications and accessibility handoffs are not connected or assumed complete.')
    st.markdown('**Metric definitions**')
    st.write(f'Data completeness: {len(tickets)-len(invalid)} / {len(tickets)} received. Initial preview yield is calculated before any commits; capacity and review exclusions affect its denominator. Current unassigned reason coverage: {len(exceptions)} / {len(tickets)-len(board)-len(proposals)} records without a recommendation. This is a fixture measure, not agency service performance.')
    st.markdown('**Append-only application activity**')
    st.dataframe(pd.DataFrame(local_rows(store.history())),hide_index=True,width='stretch')
    confirmed=st.checkbox('I confirm resetting the local schedule; preserve tickets and activity history')
    if st.button('Reset demo schedule',disabled=not confirmed): store.reset(actor,confirmed); st.rerun()
