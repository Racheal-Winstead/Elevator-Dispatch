"""Simulated dispatcher messaging (DEMO). No SMS/push, no phone numbers.

A message about a work order may go only to someone who is on duty and has no
overlapping assignment, using the same checks as scheduling. An urgent message
to a busy (but on-duty) person needs the dispatcher to confirm after seeing
the conflict; it never changes the person's existing assignment.
"""
from __future__ import annotations

import pandas as pd

import engine as eng

ACK_TIMEOUT_MIN = 15  # same default for normal and urgent messages; configurable
RESPONSES = ("ACKNOWLEDGED", "CANNOT_RESPOND", "DECLINED")


def relevant_slot(ticket_id: str, assignments: list[dict], now: pd.Timestamp = eng.DEMO_NOW) -> str:
    """Slot the message is about: the ticket's slot if assigned, else the current/next slot."""
    for g in assignments:
        if g["ticket_id"] == ticket_id:
            return g["slot"]
    hhmm = now.strftime("%H:%M")
    for slot, (start, end) in eng.SLOTS.items():
        if hhmm < end:
            return slot
    return list(eng.SLOTS)[-1]


def check_recipient(tech: dict, ticket_id: str, assignments: list[dict], now: pd.Timestamp = eng.DEMO_NOW):
    """Return None if OK, else (reason_code, detail, can_override)."""
    if tech["active"] != "Y" or tech["attendance_state"] != "PRESENT":
        return "MESSAGE_BLOCKED_OFF_DUTY", f"{tech['name']} is not present on duty", False
    slot = relevant_slot(ticket_id, assignments, now)
    if not eng.in_shift(tech, slot):
        return "MESSAGE_BLOCKED_OFF_DUTY", f"{tech['name']} is off shift in {slot}", False
    other = eng.is_busy(tech["tech_id"], slot, assignments)
    if other and other != ticket_id:
        return "MESSAGE_BLOCKED_CONFLICT", f"{tech['name']} is already on {other} in {slot}", True
    return None


def send_message(*, ticket_id, tech, body, urgent, sender, assignments, messages, now,
                 confirm_conflict=False):
    """Try to send. Returns (message_or_None, blocked_info_or_None). Appends to `messages`."""
    block = check_recipient(tech, ticket_id, assignments, eng.DEMO_NOW)
    confirmed_by = ""
    if block:
        code, detail, can_override = block
        if not (can_override and urgent and confirm_conflict):
            return None, (code, detail, can_override and urgent)
        confirmed_by = sender
    msg = {
        "message_id": f"M-{len(messages) + 1:03d}",
        "ticket_id": ticket_id,
        "recipient_id": tech["tech_id"],
        "recipient": tech["name"],
        "sender": sender,
        "body": body,
        "urgency": "URGENT" if urgent else "NORMAL",
        "delivery_state": "SIMULATED",
        "sent_at": now,
        "response": "",
        "response_reason": "",
        "responded_at": None,
        "conflict_confirmed_by": confirmed_by,
    }
    messages.append(msg)
    return msg, None


def respond(msg: dict, response: str, now: pd.Timestamp, reason: str = "") -> None:
    if response not in RESPONSES:
        raise ValueError(f"response must be one of {RESPONSES}")
    if response == "CANNOT_RESPOND" and not reason.strip():
        raise ValueError("A reason is required for CANNOT_RESPOND")
    msg["response"], msg["response_reason"], msg["responded_at"] = response, reason, now


def no_ack(messages: list[dict], now: pd.Timestamp, timeout_min: int = ACK_TIMEOUT_MIN) -> list[dict]:
    """Messages with no response after the time limit."""
    limit = pd.Timedelta(minutes=timeout_min)
    return [m for m in messages if not m["response"] and now - m["sent_at"] >= limit]
