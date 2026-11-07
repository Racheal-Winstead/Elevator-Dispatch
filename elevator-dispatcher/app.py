"""Elevator Dispatcher -- NYCHA dispatcher workbench (DEMO MVP).

Run:  streamlit run app.py
All screens live here; all scheduling rules live in engine.py.
"""
from __future__ import annotations

import time
from datetime import datetime

import pandas as pd
import streamlit as st

import agents
import engine as eng
import messaging as msgs

st.set_page_config(page_title="Elevator Dispatcher (Demo)", layout="wide")


# ----------------------------------------------------------------------------
# State helpers
# ----------------------------------------------------------------------------
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(event_type, entity, old="", new="", reason=""):
    """Append-only activity log. Entries are never edited or deleted."""
    ss = st.session_state
    ss.audit.append({
        "event_id": len(ss.audit) + 1,
        "time": now_str(),
        "actor": ss.get("dispatcher", "Dispatcher (demo)"),
        "event_type": event_type,
        "entity": entity,
        "old_value": old,
        "new_value": new,
        "reason": reason,
        "source": "DEMO SEED",
    })


def init_state():
    ss = st.session_state
    if "loaded" in ss:
        return
    src = ss.get("source", "tickets.csv")
    if src == "Mock Maximo feed":
        import maximo_mock
        tickets, info = eng.load_tickets_from_maximo(maximo_mock.to_maximo())
    else:
        tickets, info = eng.load_tickets()
    ss.tickets = tickets
    ss.info = info
    ss.staff = eng.load_staff()
    ss.assignments = []
    ss.next_group = 1
    ss.status = {t: "UNASSIGNED" for t in tickets["ticket_id"]}
    ss.meta = {}  # per-ticket: last_update, next_action, owner
    ss.acks = {}  # escalation acknowledgements
    ss.confirmed = set()  # hazards the dispatcher confirmed
    ss.audit = []
    ss.messages = []
    ss.clock_min = 0  # demo clock offset for acknowledgement timeouts
    ss.ran = False
    ss.last_run_ms = None
    ss.loaded_at = now_str()
    ss.loaded = True
    log("IMPORT", src, new=f"{info['rows_read']} rows read", reason="DEMO SEED data loaded")
    for tid in info["duplicate_ids_dropped"]:
        log("DUPLICATE_ID_DROPPED", tid, reason="Same ticket ID appeared twice; kept the last copy")
    for r in tickets[tickets["data_status"] != "OK"].to_dict("records"):
        log("VALIDATION", r["ticket_id"], new=r["data_status"], reason=r["issues"])


def view() -> pd.DataFrame:
    """Tickets plus triage, status, crew and flags -- one table for the screens."""
    ss = st.session_state
    df = eng.with_triage(ss.tickets, ss.confirmed)
    by_ticket = {g["ticket_id"]: g for g in ss.assignments}
    names = {t["tech_id"]: t["name"] for t in ss.staff}
    df["status"] = df["ticket_id"].map(ss.status)
    df["slot"] = df["ticket_id"].map(lambda t: by_ticket[t]["slot"] if t in by_ticket else "")
    df["crew"] = df["ticket_id"].map(
        lambda t: " + ".join(f"{r}: {names[i]}" for r, i in by_ticket[t]["crew"].items()) if t in by_ticket else ""
    )
    df["age"] = [
        f"{int((eng.DEMO_NOW - d).total_seconds() // 3600)}h {int((eng.DEMO_NOW - d).total_seconds() // 60 % 60)}m"
        if pd.notna(d) else ""
        for d in df["reported_dt"]
    ]
    flags = []
    for r in df.to_dict("records"):
        f = []
        if r["data_status"] != "OK":
            f.append(r["data_status"])
        if r["possible_dup_of"]:
            f.append(f"POSSIBLE_DUPLICATE of {r['possible_dup_of']}")
        if r["hazard_keyword"] and r["data_status"] == "OK" and r["ticket_id"] not in ss.confirmed:
            f.append("HAZARD_REVIEW_REQUIRED")
        flags.append("; ".join(f))
    df["flags"] = flags
    return df


def unassigned_reasons(df: pd.DataFrame) -> dict:
    """{ticket_id: [(code, detail)]} for valid tickets with no crew (after a run)."""
    ss = st.session_state
    out = {}
    if not ss.ran:
        return out
    assigned = {g["ticket_id"] for g in ss.assignments}
    for r in df[df["data_status"] == "OK"].to_dict("records"):
        if r["ticket_id"] not in assigned:
            out[r["ticket_id"]] = eng.explain_unassigned(r, ss.assignments, ss.staff)
    return out


def set_status(tid, new, note="", owner="", reason=""):
    ss = st.session_state
    old = ss.status.get(tid, "")
    ss.status[tid] = new
    m = ss.meta.setdefault(tid, {})
    m["last_update"] = now_str()
    if note:
        m["next_action"] = note
    if owner:
        m["owner"] = owner
    log("STATUS_CHANGE", tid, old, new, reason or note)


def commit_group(ticket_id, slot, crew, source):
    ss = st.session_state
    gid = f"G-{ss.next_group:03d}"
    ss.next_group += 1
    ss.assignments.append({
        "group_id": gid, "ticket_id": ticket_id, "slot": slot, "crew": crew,
        "source": source, "rule_version": eng.RULE_VERSION,
    })
    set_status(ticket_id, "ASSIGNED", reason=f"{source} assignment {gid} in {slot}")
    log("ASSIGN", ticket_id, "", f"{gid} {slot} {crew}", source)
    return gid


def tech_name(tid):
    return next((t["name"] for t in st.session_state.staff if t["tech_id"] == tid), tid)


# ----------------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------------
def tab_queue(df):
    ss = st.session_state
    st.subheader("Work queue")
    c1, c2, c3, c4 = st.columns(4)
    f_triage = c1.multiselect("Triage", list(eng.TRIAGE_LABELS.values()))
    f_boro = c2.multiselect("Borough", sorted(x for x in df["borough"].unique() if x))
    f_status = c3.multiselect("Status", eng.STATUSES)
    f_data = c4.multiselect("Data quality", sorted(df["data_status"].unique()))
    q = df
    if f_triage:
        q = q[q["triage_label"].isin(f_triage)]
    if f_boro:
        q = q[q["borough"].isin(f_boro)]
    if f_status:
        q = q[q["status"].isin(f_status)]
    if f_data:
        q = q[q["data_status"].isin(f_data)]
    q = eng.priority_order(q[q["data_status"] == "OK"]) if not f_data else q
    cols = ["ticket_id", "triage_label", "source_priority", "borough", "building", "work_type",
            "description", "age", "status", "slot", "crew", "flags", "triage_why"]
    st.dataframe(q[cols], hide_index=True, use_container_width=True)
    st.caption("Queue is ordered: confirmed hazards, then critical service impact, then source priority, "
               "oldest first, then ticket ID. 'Triage why' shows the rule behind each label.")

    st.subheader("Review queue (needs a human)")
    bad = df[df["data_status"] != "OK"]
    st.markdown("**Tickets with data problems** -- not scheduled, not deleted")
    if bad.empty:
        st.write("None.")
    else:
        st.dataframe(bad[["ticket_id", "data_status", "issues", "borough", "description"]],
                     hide_index=True, use_container_width=True)
    if ss.info["duplicate_ids_dropped"]:
        st.info("Exact repeats of a ticket ID were found and the last copy was kept: "
                + ", ".join(ss.info["duplicate_ids_dropped"]) + ". Logged in the activity log.")
    dups = df[df["possible_dup_of"] != ""]
    st.markdown("**Possible duplicates** -- flagged only, nothing is merged")
    if dups.empty:
        st.write("None.")
    else:
        st.dataframe(dups[["ticket_id", "possible_dup_of", "elevator_asset_id", "reported_at", "description"]],
                     hide_index=True, use_container_width=True)
    st.markdown("**Possible hazards (wording only, not confirmed)**")
    hz = df[(df["hazard_keyword"]) & (df["data_status"] == "OK") & (~df["ticket_id"].isin(ss.confirmed))]
    if hz.empty:
        st.write("None.")
    else:
        st.dataframe(hz[["ticket_id", "borough", "description", "triage_label"]],
                     hide_index=True, use_container_width=True)
        st.caption("The app never declares an emergency from words alone. A dispatcher must confirm "
                   "(and follow the approved 911/FDNY procedure).")
        c1, c2 = st.columns([2, 1])
        pick = c1.selectbox("Ticket to review", hz["ticket_id"].tolist(), key="hz_pick")
        if c2.button("Confirm as hazard (T1)", key="hz_btn"):
            ss.confirmed.add(pick)
            log("HAZARD_CONFIRMED", pick, "keyword flag only", "T1 confirmed by dispatcher",
                "Dispatcher confirmation")
            st.rerun()


def tab_crew(df):
    ss = st.session_state
    st.subheader("Crew roster and today's board")
    st.caption("DEMO roster (10 people, 4 slots). Not NYCHA's real staffing. UNKNOWN attendance is never treated as available.")
    rows = []
    for t in ss.staff:
        blk = eng.tech_block(t)
        rows.append({
            "id": t["tech_id"], "name": t["name"], "role": t["role"] + (" (float)" if t["float_helper"] == "Y" else ""),
            "attendance": t["attendance_state"], "shift": f"{t['shift_start']}-{t['shift_end']}",
            "authorized": ", ".join(t["boroughs"]),
            "certification": f"{t['certification_status']} {t['certification_expiry']}".strip(),
            "schedulable": "YES" if not blk else f"NO - {blk[0]}: {blk[1]}",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.markdown("**Slot board** (who is on which ticket)")
    board = []
    for t in ss.staff:
        row = {"person": f"{t['name']} ({t['tech_id']})"}
        for s in eng.SLOTS:
            if eng.tech_block(t):
                row[s] = "not available"
            elif not eng.in_shift(t, s):
                row[s] = "off shift"
            else:
                row[s] = eng.is_busy(t["tech_id"], s, ss.assignments) or "free"
        board.append(row)
    st.dataframe(pd.DataFrame(board), hide_index=True, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Time slots (demo)**")
        st.dataframe(pd.DataFrame([{"slot": s, "start": a, "end": b} for s, (a, b) in eng.SLOTS.items()]),
                     hide_index=True, use_container_width=True)
    with c2:
        st.markdown("**Crew needed by work type (DEMO-CONFIGURED)**")
        st.dataframe(pd.DataFrame([{"work type": k, "roles needed": " + ".join(v)} for k, v in eng.CREW_RULES.items()]),
                     hide_index=True, use_container_width=True)


def tab_schedule(df):
    ss = st.session_state
    st.subheader("Schedule")
    ok = df[df["data_status"] == "OK"]
    assigned_ids = {g["ticket_id"] for g in ss.assignments}
    reasons = unassigned_reasons(df)

    if st.button("Run auto-schedule", type="primary"):
        t0 = time.perf_counter()
        new = eng.auto_schedule(df, ss.staff, ss.assignments, start_id=ss.next_group)
        ss.last_run_ms = (time.perf_counter() - t0) * 1000
        for g in new:
            ss.next_group += 1
            ss.assignments.append(g)
            set_status(g["ticket_id"], "ASSIGNED", reason=f"AUTO assignment {g['group_id']} in {g['slot']}")
            log("ASSIGN", g["ticket_id"], "", f"{g['group_id']} {g['slot']} {g['crew']}", f"AUTO {eng.RULE_VERSION}")
        ss.ran = True
        log("AUTO_SCHEDULE_RUN", "schedule", new=f"{len(new)} crews assigned", reason=f"{ss.last_run_ms:.1f} ms")
        st.rerun()

    n_assigned = len(assigned_ids & set(ok["ticket_id"]))
    n_un = len(ok) - n_assigned
    n_review = int((df["data_status"] != "OK").sum())
    viol = eng.integrity_violations(ss.assignments, ss.tickets, ss.staff)
    m = st.columns(5)
    m[0].metric("Valid tickets", len(ok))
    m[1].metric("Assigned", n_assigned)
    m[2].metric("Unassigned", n_un)
    m[3].metric("In review (bad data)", n_review)
    m[4].metric("Rule violations", viol)
    rate = f"{n_assigned / len(ok):.0%}" if len(ok) else "n/a"
    st.caption(
        f"First-pass assignment rate = assigned / valid tickets = {n_assigned}/{len(ok)} = {rate}. "
        f"Reconciliation: {n_assigned} assigned + {n_un} unassigned + {n_review} in review = {len(df)} tickets. "
        + (f"Last scheduler run: {ss.last_run_ms:.1f} ms." if ss.last_run_ms is not None else "Scheduler has not been run yet.")
    )
    st.warning(f"EXISTING_COMMITMENT_UNKNOWN: {eng.REASON_HELP['EXISTING_COMMITMENT_UNKNOWN']}")

    st.markdown("**Assignments**")
    if ss.assignments:
        st.dataframe(pd.DataFrame([{
            "group": g["group_id"], "ticket": g["ticket_id"], "slot": f"{g['slot']} ({'-'.join(eng.SLOTS[g['slot']])})",
            "crew": " + ".join(f"{r}: {tech_name(i)}" for r, i in g["crew"].items()), "by": g["source"],
        } for g in ss.assignments]), hide_index=True, use_container_width=True)
    else:
        st.write("No assignments yet. Press **Run auto-schedule**.")

    st.markdown("**Unassigned work and why**")
    if not ss.ran:
        st.write("Run the scheduler to see reason codes.")
    elif not reasons:
        st.success("Every valid ticket has a crew.")
    else:
        byid = df.set_index("ticket_id")
        st.dataframe(pd.DataFrame([{
            "ticket": tid, "triage": byid.loc[tid, "triage_label"], "borough": byid.loc[tid, "borough"],
            "reason codes": ", ".join(c for c, _ in rs), "details": " | ".join(d for _, d in rs),
        } for tid, rs in reasons.items()]), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.markdown("**Manual assign** -- uses the same rule checker as auto-schedule")
    free = ok[~ok["ticket_id"].isin(assigned_ids)]
    if free.empty:
        st.write("No unassigned valid tickets.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        tid = c1.selectbox("Ticket", free["ticket_id"].tolist(), key="m_ticket")
        slot = c2.selectbox("Slot", list(eng.SLOTS), key="m_slot")
        ticket = ok[ok["ticket_id"] == tid].iloc[0].to_dict()
        roles = eng.CREW_RULES[ticket["work_type"]]
        mechs = {f"{t['name']} ({t['tech_id']})": t["tech_id"] for t in ss.staff if t["role"] == "Mechanic"}
        helps = {f"{t['name']} ({t['tech_id']})": t["tech_id"] for t in ss.staff if t["role"] == "Helper"}
        mech = mechs[c3.selectbox("Mechanic", list(mechs), key="m_mech")]
        crew = {"Mechanic": mech}
        if "Helper" in roles:
            crew["Helper"] = helps[c4.selectbox("Helper", list(helps), key="m_help")]
        else:
            c4.caption("No helper needed for this work type.")
        check = agents.conflict_check_agent(ticket, slot, crew, ss.assignments, ss.staff)
        errs = check["findings"]  # validator result; the agent only reports it
        st.caption("Conflict-check agent: " + ("no conflicts found" if check["ok"] else f"{len(errs)} problem(s) found"))
        if errs:
            st.error("Preview: this change would be REJECTED\n\n" + "\n".join(f"- **{c}**: {m_}" for c, m_ in errs))
        else:
            st.success(f"Preview: valid. {tid} gets {' + '.join(tech_name(i) for i in crew.values())} in {slot}.")
        if st.button("Assign crew"):
            errs = eng.validate_assignment(ticket, slot, crew, ss.assignments, ss.staff)
            if errs:
                log("MANUAL_CONFLICT", tid, "unchanged", "rejected", "; ".join(f"{c}: {m_}" for c, m_ in errs))
                st.error("Rejected. Nothing was changed. " + "; ".join(c for c, _ in errs))
            else:
                commit_group(tid, slot, crew, "MANUAL")
                st.rerun()

    st.markdown("**Remove an assignment** (whole crew is removed together)")
    if ss.assignments:
        opts = {f"{g['group_id']} - {g['ticket_id']} in {g['slot']}": g["group_id"] for g in ss.assignments}
        pick = st.selectbox("Assignment", list(opts), key="rm_pick")
        st.caption("Preview: the ticket returns to UNASSIGNED and everyone on the crew is freed for that slot.")
        if st.button("Remove assignment"):
            gid = opts[pick]
            g = next(x for x in ss.assignments if x["group_id"] == gid)
            ss.assignments = [x for x in ss.assignments if x["group_id"] != gid]
            set_status(g["ticket_id"], "UNASSIGNED", reason=f"Assignment {gid} removed")
            log("UNASSIGN", g["ticket_id"], gid, "removed", "Dispatcher removed crew")
            st.rerun()


def tab_progress(df):
    ss = st.session_state
    st.subheader("Escalations")
    reasons = unassigned_reasons(df)
    urgent = [t for t in reasons if df.set_index("ticket_id").loc[t, "triage"] == 1]
    if not ss.ran:
        st.write("Run the scheduler to check for unstaffed emergencies.")
    elif not urgent:
        st.success("No unstaffed emergencies.")
    for tid in urgent:
        row = df.set_index("ticket_id").loc[tid]
        st.error(
            f"**{tid} - {row['triage_label']}** in {row['borough']} ({row['building']}, {row['development']}). "
            f"Reason: {'; '.join(c for c, _ in reasons[tid])}. "
            "Required human action: follow the approved emergency / 911 / FDNY procedure and notify a supervisor. "
            "This tool does not dispatch emergencies."
        )
        ack = ss.acks.get(tid)
        if ack:
            st.write(f"Acknowledged by **{ack['by']}** at {ack['time']}: {ack['action']} (owner: {ack['owner']})")
        else:
            with st.form(f"ack_{tid}"):
                a = st.text_input("Action taken", key=f"ack_a_{tid}")
                o = st.text_input("Responsible person / team", key=f"ack_o_{tid}")
                if st.form_submit_button("Acknowledge escalation"):
                    if not a.strip() or not o.strip():
                        st.error("Please enter the action taken and who is responsible.")
                    else:
                        ss.acks[tid] = {"by": ss.get("dispatcher", "Dispatcher (demo)"), "time": now_str(), "action": a, "owner": o}
                        log("ESCALATION_ACK", tid, "", a, f"owner: {o}")
                        ss.meta.setdefault(tid, {}).update({"last_update": now_str(), "owner": o, "next_action": a})
                        st.rerun()

    st.subheader("Update work status")
    st.caption("Status changes here are dispatcher-entered (not from a field app or Maximo).")
    valid = df[df["data_status"] == "OK"]["ticket_id"].tolist()
    c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
    tid = c1.selectbox("Ticket", valid, key="s_ticket")
    new = c2.selectbox("New status", eng.STATUSES, key="s_new")
    note = c3.text_input("Next action / blocker note", key="s_note")
    owner = c4.text_input("Owner", key="s_owner")
    if st.button("Save status"):
        cur = ss.status[tid]
        has_crew = any(g["ticket_id"] == tid for g in ss.assignments)
        if new in ("ASSIGNED", "EN_ROUTE", "ON_SITE", "RESTORED") and not has_crew:
            st.error(f"{new} needs an assigned crew first. Nothing changed.")
        elif new == "UNASSIGNED" and has_crew:
            st.error("Remove the assignment on the Schedule tab instead. Nothing changed.")
        elif new == "CLOSED" and cur != "RESTORED":
            st.error("A ticket can only be CLOSED after it is RESTORED (restored = service back; closed = paperwork done). Nothing changed.")
        elif new == "BLOCKED" and not note.strip():
            st.error("A BLOCKED ticket needs a note saying what is blocking it / the next action.")
        else:
            set_status(tid, new, note, owner)
            st.rerun()

    st.subheader("Progress")
    rows = []
    for r in eng.priority_order(df[df["data_status"] == "OK"]).to_dict("records"):
        m = ss.meta.get(r["ticket_id"], {})
        rows.append({
            "ticket": r["ticket_id"], "triage": r["triage_label"], "status": ss.status[r["ticket_id"]],
            "crew": r["crew"], "slot": r["slot"], "time since report": r["age"],
            "last update": m.get("last_update", ""), "next action": m.get("next_action", ""), "owner": m.get("owner", ""),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def tab_messages(df):
    ss = st.session_state
    now = eng.DEMO_NOW + pd.Timedelta(minutes=ss.clock_min)
    st.subheader("Message on-duty staff (SIMULATED)")
    st.info("Messages stay inside this demo (no SMS, no phone numbers). A message is blocked if the person is "
            "off duty or already booked in the same slot.")
    ok = df[df["data_status"] == "OK"]
    if ok.empty:
        st.write("No valid tickets.")
        return
    tid = st.selectbox("Work order", ok["ticket_id"].tolist(), key="msg_ticket")
    t = ok.set_index("ticket_id").loc[tid].to_dict()
    t["ticket_id"] = tid
    slot = msgs.relevant_slot(tid, ss.assignments, eng.DEMO_NOW)

    st.markdown("**Availability agent** (advisory; answers come from the shared validator)")
    avail = agents.availability_agent(t, ss.assignments, ss.staff, slot=slot)[slot]
    for role, r in avail.items():
        names = ", ".join(c["name"] + (" (float)" if c["float_helper"] else "") for c in r["available"]) or "none"
        st.write(f"{role}s available in {slot}: {names}")
        if r["excluded"]:
            with st.expander(f"Why others are not available as {role}"):
                st.table(pd.DataFrame(r["excluded"], columns=["Person", "Reason code", "Detail"]))

    by_t = {g["ticket_id"]: g for g in ss.assignments}
    crew_names = {r: tech_name(i) for r, i in by_t[tid]["crew"].items()} if tid in by_t else {}
    urgent = st.checkbox("Urgent", value=bool(t["triage"] == 1), key="msg_urgent")
    draft = agents.notification_draft(t, slot, crew_names, urgent)
    body = st.text_area("Message (agent draft - edit before sending)", value=draft, key=f"msg_body_{tid}_{int(urgent)}")
    recips = [x for x in ss.staff]
    labels = {f"{x['name']} ({x['role']})": x for x in recips}
    tech = labels[st.selectbox("Send to", list(labels), key="msg_to")]
    block = msgs.check_recipient(tech, tid, ss.assignments, eng.DEMO_NOW)
    confirm = False
    if block:
        code, detail, can_override = block
        st.warning(f"{code}: {detail}")
        if can_override and urgent:
            confirm = st.checkbox("I have seen this conflict and want to send this urgent message anyway "
                                  "(their existing assignment will not change)", key="msg_confirm")
    if st.button("Send message"):
        m, blocked = msgs.send_message(ticket_id=tid, tech=tech, body=body, urgent=urgent,
                                       sender=ss.get("dispatcher", "Dispatcher (demo)"),
                                       assignments=ss.assignments, messages=ss.messages, now=now,
                                       confirm_conflict=confirm)
        if blocked:
            st.error(f"Not sent - {blocked[0]}: {blocked[1]}")
            log("MESSAGE_BLOCKED", tid, "", tech["tech_id"], blocked[0])
        else:
            log("MESSAGE_SENT", tid, "", f"{m['message_id']} to {tech['tech_id']}",
                "URGENT, conflict confirmed by dispatcher" if m["conflict_confirmed_by"] else m["urgency"])
            st.success(f"Sent {m['message_id']} to {tech['name']} (simulated).")

    st.markdown("---")
    c1, c2 = st.columns([3, 1])
    c1.caption(f"Demo clock {now:%H:%M} | acknowledgement limit {msgs.ACK_TIMEOUT_MIN} minutes")
    if c2.button("Simulate 15 minutes passing"):
        ss.clock_min += 15
        for m in msgs.no_ack(ss.messages, eng.DEMO_NOW + pd.Timedelta(minutes=ss.clock_min)):
            if not m.get("no_ack_logged"):
                m["no_ack_logged"] = True
                log("NO_ACK", m["ticket_id"], "", m["message_id"], f"{m['recipient']} did not respond")
        st.rerun()
    late = msgs.no_ack(ss.messages, now)
    for m in late:
        st.error(f"NO_ACK: {m['message_id']} to {m['recipient']} about {m['ticket_id']} - no reply after "
                 f"{msgs.ACK_TIMEOUT_MIN} minutes. Follow up with the crew or reassign.")

    st.subheader("Outbox / inbox")
    if not ss.messages:
        st.write("No messages yet.")
    for m in ss.messages:
        st.write(f"**{m['message_id']}** [{m['urgency']}] to {m['recipient']} about {m['ticket_id']} "
                 f"({m['delivery_state']}) - response: {m['response'] or 'none yet'}"
                 + (f" ({m['response_reason']})" if m["response_reason"] else ""))
        if not m["response"]:
            c1, c2, c3 = st.columns([2, 2, 3])
            resp = c1.selectbox("Recipient replies", msgs.RESPONSES, key=f"r_{m['message_id']}")
            why = c2.text_input("Reason (if cannot respond)", key=f"w_{m['message_id']}")
            if c3.button("Record reply", key=f"b_{m['message_id']}"):
                try:
                    msgs.respond(m, resp, now, why)
                except ValueError as e:
                    st.error(str(e))
                else:
                    log("MESSAGE_RESPONSE", m["ticket_id"], "", f"{m['message_id']} {resp}", why)
                    if resp == "ACKNOWLEDGED" and ss.status.get(m["ticket_id"]) == "ASSIGNED":
                        set_status(m["ticket_id"], "ACKNOWLEDGED", reason=f"{m['recipient']} acknowledged {m['message_id']}")
                    st.rerun()

    st.subheader("Conflict-check agent")
    st.caption("Runs on every manual assignment on the Schedule tab and on every message above. "
               "It is advisory; the validator is the rule.")

    st.subheader("Intake agent (advisory)")
    st.caption("Flags tickets for a human to look at. It never declares an emergency and changes nothing.")
    found = agents.intake_agent(ss.tickets.to_dict("records"))
    if found:
        st.dataframe(pd.DataFrame([{"ticket_id": f["ticket_id"],
                                    "flags": "; ".join(f"{c}: {d}" for c, d in f["flags"])} for f in found]),
                     hide_index=True, use_container_width=True)
    else:
        st.write("Nothing to flag.")

    st.subheader("Exception explainer (advisory)")
    codes = sorted(eng.REASON_HELP)
    code = st.selectbox("Reason code", codes, key="explain_code")
    ex = agents.exception_explainer(code)
    st.write(f"**What it means:** {ex['plain']}")
    st.write(f"**Next human action:** {ex['next_action']}")

    st.subheader("Handover agent (advisory draft)")
    st.text_area("Draft shift summary from the activity log (edit freely; nothing is saved or sent)",
                 agents.handover_agent(ss.audit), height=220, key="handover_draft")



def handover_table(df) -> pd.DataFrame:
    ss = st.session_state
    reasons = unassigned_reasons(df)
    rows = []
    for r in eng.priority_order(df[df["data_status"] == "OK"]).to_dict("records"):
        tid = r["ticket_id"]
        st_ = ss.status[tid]
        if st_ == "CLOSED":
            continue
        m = ss.meta.get(tid, {})
        ack = ss.acks.get(tid)
        rows.append({
            "ticket_id": tid, "triage": r["triage_label"], "borough": r["borough"], "building": r["building"],
            "status": st_, "crew": r["crew"], "slot": r["slot"],
            "blocker_or_reason": (m.get("next_action", "") if st_ == "BLOCKED" else "") or "; ".join(c for c, _ in reasons.get(tid, [])),
            "last_update": m.get("last_update", ""), "next_action": m.get("next_action", ""),
            "owner": m.get("owner", ""), "escalation_owner": ack["owner"] if ack else "",
        })
    for r in df[df["data_status"] != "OK"].to_dict("records"):
        rows.append({
            "ticket_id": r["ticket_id"], "triage": "", "borough": r["borough"], "building": r["building"],
            "status": "NEEDS REVIEW", "crew": "", "slot": "", "blocker_or_reason": f"{r['data_status']}: {r['issues']}",
            "last_update": "", "next_action": "Fix data in source", "owner": "", "escalation_owner": "",
        })
    return pd.DataFrame(rows)


def tab_reports(df):
    ss = st.session_state
    st.subheader("Reports")
    ho = handover_table(df)
    asg = pd.DataFrame([{
        "group": g["group_id"], "ticket_id": g["ticket_id"], "slot": g["slot"],
        "slot_times": "-".join(eng.SLOTS[g["slot"]]),
        "crew": " + ".join(f"{r}: {tech_name(i)}" for r, i in g["crew"].items()), "assigned_by": g["source"],
        "rule_version": g["rule_version"],
    } for g in ss.assignments])
    c1, c2 = st.columns(2)
    c1.download_button("Download shift handover (CSV)", ho.to_csv(index=False), "shift_handover.csv", "text/csv")
    c2.download_button("Download assignments (CSV)", asg.to_csv(index=False) if not asg.empty else "no assignments yet\n",
                       "assignments.csv", "text/csv")
    st.markdown("**Shift handover preview** (all open work, unassigned work and records needing review)")
    st.dataframe(ho, hide_index=True, use_container_width=True)

    with st.expander("How the numbers are calculated"):
        st.markdown(
            "- **Valid tickets**: tickets with every required field and a known work type.\n"
            "- **First-pass assignment rate**: assigned / valid tickets after one auto-schedule run.\n"
            "- **Reconciliation**: assigned + unassigned + in review = all tickets loaded (after exact repeats of a ticket ID are removed).\n"
            "- **Rule violations**: every committed assignment is re-checked against the hard rules; must be 0.\n"
            "- **Not measured here**: real-world repair time or elevator uptime. This demo cannot show those.\n"
            "- All rules, crews, slots and certifications are **DEMO-CONFIGURED**, not NYCHA policy."
        )
    with st.expander("Reason code glossary"):
        st.dataframe(pd.DataFrame([{"code": k, "meaning": v} for k, v in eng.REASON_HELP.items()]),
                     hide_index=True, use_container_width=True)

    st.subheader("Activity log (append-only)")
    st.dataframe(pd.DataFrame(ss.audit).iloc[::-1], hide_index=True, use_container_width=True)
    st.download_button("Download activity log (CSV)", pd.DataFrame(ss.audit).to_csv(index=False),
                       "activity_log.csv", "text/csv")


# ----------------------------------------------------------------------------
# Page
# ----------------------------------------------------------------------------
def main():
    ss = st.session_state
    with st.sidebar:
        st.header("Dispatcher")
        pick = st.selectbox("Ticket source", ["tickets.csv", "Mock Maximo feed"], key="source_pick",
                            help="Both are local demo data. Switching reloads tickets and clears the schedule and log.")
    if pick != ss.get("source", "tickets.csv"):
        ss.source = pick
        ss.pop("loaded", None)
    init_state()

    with st.sidebar:
        ss.dispatcher = st.text_input("Your name", value=ss.get("dispatcher", "Dispatcher (demo)"))
        st.markdown("---")
        st.markdown("**Reset schedule**")
        st.caption("Clears assignments, statuses and acknowledgements. Keeps tickets and the activity log.")
        sure = st.checkbox("Yes, reset the schedule")
        if st.button("Reset schedule", disabled=not sure):
            n = len(ss.assignments)
            ss.assignments = []
            ss.status = {t: "UNASSIGNED" for t in ss.tickets["ticket_id"]}
            ss.meta, ss.acks, ss.ran, ss.last_run_ms = {}, {}, False, None
            log("RESET", "schedule", f"{n} assignments", "0 assignments", "Dispatcher reset (tickets and log kept)")
            st.rerun()

    st.title("Elevator Dispatcher")
    st.error(
        "**DEMO SEED DATA** -- not connected to Maximo, REMS, staffing systems or emergency dispatch. "
        "This tool does not replace 911/FDNY or any NYCHA procedure."
    )
    st.caption(
        f"Source: {ss.get('source', 'tickets.csv')} + staff.csv (synthetic) | Loaded {ss.loaded_at} | {ss.info['rows_read']} rows read | "
        f"Live feed fallback: not used | Rule version {eng.RULE_VERSION} | Demo clock {eng.DEMO_NOW:%Y-%m-%d %H:%M}"
    )

    df = view()
    tabs = st.tabs(["1. Queue", "2. Crew", "3. Schedule", "4. Progress & escalations", "5. Reports & log", "6. Messages & agents"])
    with tabs[0]:
        tab_queue(df)
    with tabs[1]:
        tab_crew(df)
    with tabs[2]:
        tab_schedule(df)
    with tabs[3]:
        tab_progress(df)
    with tabs[4]:
        tab_reports(df)
    with tabs[5]:
        tab_messages(df)


if __name__ == "__main__":
    main()
