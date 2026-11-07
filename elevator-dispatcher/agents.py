"""Assistant agents (DEMO). They DRAFT, FLAG, EXPLAIN, FIND AVAILABLE PEOPLE and
CHECK CONFLICTS -- they never assign, send, change status or override the validator.

Availability and conflict answers always come from engine.py (the shared
validator). An agent saying "conflict-free" has no effect unless the validator
agrees. The scheduler itself is deterministic code, not an LLM.
"""
from __future__ import annotations

import engine as eng

AGENT_VERSION = "agents-v0.1"


class AgentWriteDenied(Exception):
    """Raised if anything asks an agent to change schedule, status or messages."""


def attempt_action(agent: str, action: str):
    """Agents have no write path. Any attempt is refused (caller should log it)."""
    raise AgentWriteDenied(f"{agent} may not {action}; only a dispatcher can")


def availability_agent(ticket: dict, assignments: list[dict], staff: list[dict], slot: str | None = None) -> dict:
    """Who is available for this ticket? Ranked (local first, float helper last).

    Returns {slot: {role: {"available": [...], "excluded": [(name, code, detail)]}}}.
    If `slot` is None, every slot is checked.
    """
    out = {}
    for s in ([slot] if slot else list(eng.SLOTS)):
        per_role = {}
        for role in eng.CREW_RULES[ticket["work_type"]]:
            avail = eng._candidates(role, ticket, s, assignments, staff)
            avail_ids = {t["tech_id"] for t in avail}
            excluded = []
            for t in staff:
                if t["role"] != role or t["tech_id"] in avail_ids:
                    continue
                blk = eng.tech_block(t, ticket["borough"])
                if blk:
                    excluded.append((t["name"], blk[0], blk[1]))
                elif not eng.in_shift(t, s):
                    excluded.append((t["name"], "OFF_SHIFT", f"not on shift for {s}"))
                else:
                    other = eng.is_busy(t["tech_id"], s, assignments)
                    excluded.append((t["name"], "DOUBLE_BOOKED", f"already on {other} in {s}"))
            per_role[role] = {
                "available": [{"tech_id": t["tech_id"], "name": t["name"],
                               "float_helper": t["float_helper"] == "Y"} for t in avail],
                "excluded": excluded,
            }
        out[s] = per_role
    return out


def conflict_check_agent(ticket: dict, slot: str, crew: dict, assignments: list[dict], staff: list[dict],
                         exclude_group=None) -> dict:
    """Advisory conflict report for a proposed assignment. Source: the shared validator."""
    errs = eng.validate_assignment(ticket, slot, crew, assignments, staff, exclude_group=exclude_group)
    return {"agent": "conflict_check", "version": AGENT_VERSION, "ok": not errs, "findings": errs}


def reconcile(agent_says_ok: bool, validator_errors: list) -> dict:
    """The validator always wins. Returns the final decision and whether they disagreed."""
    final_ok = not validator_errors
    return {"ok": final_ok, "disagreement": agent_says_ok != final_ok}


def notification_draft(ticket: dict, slot: str, crew_names: dict, urgent: bool) -> str:
    """Plain-text draft the dispatcher reviews before sending."""
    crew = ", ".join(f"{r}: {n}" for r, n in crew_names.items()) or "not yet assigned"
    start, end = eng.SLOTS[slot]
    head = "URGENT - " if urgent else ""
    return (
        f"{head}Work order {ticket['ticket_id']} ({ticket['work_type']}), priority {ticket['source_priority']}. "
        f"{ticket['development']}, {ticket['building']}, {ticket['borough']}"
        f"{', elevator ' + ticket['elevator_asset_id'] if ticket.get('elevator_asset_id') else ''}. "
        f"Slot {slot} ({start}-{end}). Crew: {crew}. "
        "Reply ACKNOWLEDGED, CANNOT_RESPOND (with reason) or DECLINED. "
        "For a trapped passenger or fire follow the approved emergency / 911 / FDNY procedure."
    )


# ----------------------------------------------------------------------------
# P1 advisory agents. Pure functions: they take data in and return text/flags
# out. They hold no reference to session state, the schedule or the message
# list, so they have no write path.
# ----------------------------------------------------------------------------
def intake_agent(tickets: list[dict]) -> list[dict]:
    """Flag tickets a human should look at. Never declares an emergency.

    Takes ticket records (rows of engine.load_tickets output). Returns one
    finding per ticket that has something to flag.
    """
    out = []
    for t in tickets:
        flags = []
        if t.get("data_status") in ("INVALID_TICKET_DATA", "UNKNOWN_WORK_TYPE"):
            flags.append((t["data_status"], t.get("issues", "")))
        if t.get("possible_dup_of"):
            flags.append(("POSSIBLE_DUPLICATE", f"Same elevator as {t['possible_dup_of']} within 24h"))
        if t.get("hazard_keyword"):
            flags.append(("HAZARD_REVIEW_REQUIRED",
                          "Wording suggests a hazard but the source did not confirm it; dispatcher decides"))
        if flags:
            out.append({"agent": "intake", "version": AGENT_VERSION, "ticket_id": t["ticket_id"],
                        "flags": flags, "declares_emergency": False})
    return out


def exception_explainer(code: str, detail: str = "") -> dict:
    """Reason code -> plain language + the next human action. Advice only."""
    next_action = EXCEPTION_NEXT_ACTION.get(code, "Review with the supervisor; no standard action is defined.")
    return {"agent": "exception_explainer", "version": AGENT_VERSION, "code": code,
            "plain": eng.REASON_HELP.get(code, "Unrecognised reason code."),
            "detail": detail, "next_action": next_action}


EXCEPTION_NEXT_ACTION = {
    "INVALID_TICKET_DATA": "Fix the missing or bad field in the source system, then reload.",
    "UNKNOWN_WORK_TYPE": "Correct the work type in the source system, then reload.",
    "POSSIBLE_DUPLICATE": "Compare the two tickets and decide whether they are one problem.",
    "HAZARD_REVIEW_REQUIRED": "Call to confirm or rule out a hazard. Follow the approved emergency procedure if confirmed.",
    "TECH_ABSENT": "Choose another person or ask the supervisor.",
    "ATTENDANCE_UNKNOWN": "Confirm attendance with the supervisor before using this person.",
    "NO_QUALIFIED_CREW": "Ask the supervisor about certified cover from another area.",
    "SECTOR_OR_DEPOT_MISMATCH": "Ask the supervisor to authorise cross-borough cover.",
    "OFF_SHIFT": "Wait for the next shift or ask the supervisor about overtime.",
    "NO_CAPACITY": "Move lower-priority work or ask the supervisor for extra crews.",
    "CREW_UNAVAILABLE": "Look for a helper or mechanic whose free time lines up, or split the job.",
    "DOUBLE_BOOKED": "Pick another slot or another person.",
    "EMERGENCY_ESCALATION_REQUIRED": "Escalate to the supervisor now and acknowledge the escalation.",
    "MANUAL_CONFLICT": "Nothing changed. Choose a different crew or slot.",
    "MESSAGE_BLOCKED_CONFLICT": "Message someone else, or confirm an urgent send after reading the conflict.",
    "MESSAGE_BLOCKED_OFF_DUTY": "Choose someone who is on duty.",
    "NO_ACK": "Follow up with the person or message someone else.",
    "EXISTING_COMMITMENT_UNKNOWN": "Check outside bookings by hand before relying on this schedule.",
}


def handover_agent(audit: list[dict], max_items: int = 5) -> str:
    """Draft shift summary text from the activity log. The dispatcher edits it."""
    def of(*types):
        return [e for e in audit if e["event_type"] in types]
    lines = [f"Shift handover DRAFT ({len(audit)} log entries) - review and edit before use."]
    lines.append(f"Crews assigned: {len(of('ASSIGN'))}; removed: {len(of('UNASSIGN'))}; "
                 f"manual changes rejected: {len(of('MANUAL_CONFLICT'))}.")
    lines.append(f"Status changes: {len(of('STATUS_CHANGE'))}; hazards confirmed by dispatcher: {len(of('HAZARD_CONFIRMED'))}.")
    lines.append(f"Messages sent: {len(of('MESSAGE_SENT'))}; blocked: {len(of('MESSAGE_BLOCKED'))}; "
                 f"no acknowledgement: {len(of('NO_ACK'))}.")
    bad = of("VALIDATION")
    if bad:
        lines.append("Data problems held in review: " + ", ".join(e["entity"] for e in bad) + ".")
    ack = {e["entity"] for e in of("ESCALATION_ACK")}
    lines.append("Escalations acknowledged: " + (", ".join(sorted(ack)) if ack else "none") + ".")
    blocked = [e for e in of("STATUS_CHANGE") if e["new_value"] == "BLOCKED"]
    if blocked:
        lines.append("Marked BLOCKED: " + "; ".join(
            f"{e['entity']} ({e['reason'] or 'no note'})" for e in blocked[-max_items:]))
    na = of("NO_ACK")
    if na:
        lines.append("Open follow-ups: " + "; ".join(e["reason"] for e in na[-max_items:]))
    return "\n".join(lines)
