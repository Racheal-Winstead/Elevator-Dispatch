"""P1 advisory agents: intake, exception explainer, handover."""
import inspect

import agents
import engine as eng


def _tickets():
    df, _ = eng.load_tickets()
    return df.to_dict("records")


def test_intake_flags_and_never_declares_emergency():
    out = agents.intake_agent(_tickets())
    codes = {c for f in out for c, _ in f["flags"]}
    assert {"INVALID_TICKET_DATA", "POSSIBLE_DUPLICATE", "HAZARD_REVIEW_REQUIRED"} <= codes
    assert all(f["declares_emergency"] is False for f in out)
    # a keyword-only "stuck" ticket is flagged for review, not escalated
    assert not any("EMERGENCY" in c for f in out for c, _ in f["flags"])


def test_intake_missing_field_ticket_is_flagged():
    t = {"ticket_id": "X", "data_status": "INVALID_TICKET_DATA", "issues": "Missing/invalid: building"}
    out = agents.intake_agent([t])
    assert out[0]["flags"][0][0] == "INVALID_TICKET_DATA"
    assert agents.intake_agent([{"ticket_id": "Y", "data_status": "OK"}]) == []


def test_exception_explainer_covers_every_reason_code():
    for code in eng.REASON_HELP:
        r = agents.exception_explainer(code)
        assert r["plain"] and r["next_action"] and "no standard action" not in r["next_action"]
    assert "supervisor" in agents.exception_explainer("NOPE")["next_action"]


def test_handover_summarises_log_and_does_not_mutate_it():
    audit = [
        {"event_id": 1, "event_type": "ASSIGN", "entity": "T-1", "old_value": "", "new_value": "G1", "reason": ""},
        {"event_id": 2, "event_type": "STATUS_CHANGE", "entity": "T-2", "old_value": "ASSIGNED",
         "new_value": "BLOCKED", "reason": "no key"},
        {"event_id": 3, "event_type": "NO_ACK", "entity": "T-1", "old_value": "", "new_value": "M-001",
         "reason": "Mechanic C did not respond"},
    ]
    before = [dict(e) for e in audit]
    text = agents.handover_agent(audit)
    assert "Crews assigned: 1" in text and "T-2 (no key)" in text and "Mechanic C did not respond" in text
    assert audit == before


def test_p1_agents_have_no_write_path():
    for fn in (agents.intake_agent, agents.exception_explainer, agents.handover_agent):
        src = inspect.getsource(fn)
        assert "session_state" not in src and "messages.append" not in src and "assignments.append" not in src
