"""QA-25 to QA-32: messaging and agents."""
import pandas as pd
import pytest

import agents
import engine as eng
import messaging as msgs

NOW = eng.DEMO_NOW


@pytest.fixture()
def world():
    df, _ = eng.load_tickets()
    df = eng.with_triage(df, set())
    staff = eng.load_staff()
    groups = eng.auto_schedule(df, staff, [])
    by_id = {t["tech_id"]: t for t in staff}
    tickets = {r["ticket_id"]: r for r in df.to_dict("records")}
    return df, staff, groups, by_id, tickets


def test_qa25_message_to_assigned_crew(world):
    df, staff, groups, by_id, _ = world
    g = groups[0]
    tech = by_id[next(iter(g["crew"].values()))]
    out = []
    m, blocked = msgs.send_message(ticket_id=g["ticket_id"], tech=tech, body="x", urgent=False,
                                   sender="D", assignments=groups, messages=out, now=NOW)
    assert blocked is None and m in out and m["delivery_state"] == "SIMULATED"


def _busy_pair(world):
    """(tech, other ticket) where tech is booked on one ticket and we message about another."""
    df, staff, groups, by_id, tickets = world
    g = groups[0]
    tech = by_id[next(iter(g["crew"].values()))]
    other = next(t for t in groups if t["ticket_id"] != g["ticket_id"] and t["slot"] == g["slot"])
    return tech, g, other


def test_qa26_conflict_blocked_and_assignment_untouched(world):
    df, staff, groups, by_id, tickets = world
    tech, g, other = _busy_pair(world)
    before = [dict(x) for x in groups]
    m, blocked = msgs.send_message(ticket_id=other["ticket_id"], tech=tech, body="x", urgent=False,
                                   sender="D", assignments=groups, messages=[], now=NOW)
    assert m is None and blocked[0] == "MESSAGE_BLOCKED_CONFLICT"
    assert groups == before


def test_qa27_off_duty_blocked_even_if_urgent_confirmed(world):
    df, staff, groups, by_id, _ = world
    bad = next(t for t in staff if t["attendance_state"] in ("ABSENT", "UNKNOWN"))
    m, blocked = msgs.send_message(ticket_id=groups[0]["ticket_id"], tech=bad, body="x", urgent=True,
                                   sender="D", assignments=groups, messages=[], now=NOW,
                                   confirm_conflict=True)
    assert m is None and blocked[0] == "MESSAGE_BLOCKED_OFF_DUTY"


def test_qa28_urgent_send_to_busy_tech_after_dispatcher_confirms(world):
    df, staff, groups, by_id, tickets = world
    tech, g, other = _busy_pair(world)
    before = [dict(x) for x in groups]
    out = []
    m, blocked = msgs.send_message(ticket_id=other["ticket_id"], tech=tech, body="x", urgent=True,
                                   sender="Dana", assignments=groups, messages=out, now=NOW)
    assert m is None and blocked[2] is True  # can be confirmed
    m, blocked = msgs.send_message(ticket_id=other["ticket_id"], tech=tech, body="x", urgent=True,
                                   sender="Dana", assignments=groups, messages=out, now=NOW,
                                   confirm_conflict=True)
    assert blocked is None and m["conflict_confirmed_by"] == "Dana"
    assert groups == before  # existing assignments untouched


def test_non_urgent_cannot_be_overridden(world):
    tech, g, other = _busy_pair(world)
    _, _, groups, _, _ = world
    m, blocked = msgs.send_message(ticket_id=other["ticket_id"], tech=tech, body="x", urgent=False,
                                   sender="D", assignments=groups, messages=[], now=NOW,
                                   confirm_conflict=True)
    assert m is None


def test_qa29_no_ack_after_15_minutes(world):
    df, staff, groups, by_id, _ = world
    g = groups[0]
    tech = by_id[next(iter(g["crew"].values()))]
    out = []
    m, _ = msgs.send_message(ticket_id=g["ticket_id"], tech=tech, body="x", urgent=True,
                             sender="D", assignments=groups, messages=out, now=NOW)
    assert msgs.no_ack(out, NOW + pd.Timedelta(minutes=14)) == []
    assert msgs.no_ack(out, NOW + pd.Timedelta(minutes=15)) == [m]
    msgs.respond(m, "ACKNOWLEDGED", NOW + pd.Timedelta(minutes=16))
    assert msgs.no_ack(out, NOW + pd.Timedelta(minutes=30)) == []


def test_cannot_respond_needs_reason(world):
    m = {"response": "", "response_reason": "", "responded_at": None}
    with pytest.raises(ValueError):
        msgs.respond(m, "CANNOT_RESPOND", NOW, "")


def test_qa30_agents_have_no_write_path():
    with pytest.raises(agents.AgentWriteDenied):
        agents.attempt_action("availability", "assign a crew")
    for name in ("commit_group", "set_status", "send_message", "assign"):
        assert not hasattr(agents, name)


def test_qa31_availability_candidates_all_pass_validator(world):
    df, staff, groups, by_id, tickets = world
    unassigned = next(t for t in tickets.values()
                      if t["data_status"] == "OK" and t["ticket_id"] not in {g["ticket_id"] for g in groups})
    res = agents.availability_agent(unassigned, groups, staff)
    for slot, roles in res.items():
        for role, r in roles.items():
            for cand in r["available"]:
                errs = eng.validate_assignment(unassigned, slot, {role: cand["tech_id"]}, groups, staff)
                # only the "other role missing" complaint is allowed here
                assert all(c == "CREW_UNAVAILABLE" for c, _ in errs), errs
            for name, code, _ in r["excluded"]:
                assert code in eng.REASON_HELP
    # absent / unknown / expired people are never offered
    offered = {c["name"] for roles in res.values() for r in roles.values() for c in r["available"]}
    bad = {t["name"] for t in staff if eng.tech_block(t) is not None}
    assert not offered & bad


def test_qa32_validator_wins_over_agent_claim(world):
    df, staff, groups, by_id, tickets = world
    g = groups[0]
    busy_tech = next(iter(g["crew"].items()))
    other = next(t for t in groups if t["ticket_id"] != g["ticket_id"] and t["slot"] == g["slot"])
    t = tickets[other["ticket_id"]]
    crew = dict(other["crew"]); crew[busy_tech[0]] = busy_tech[1]
    errs = eng.validate_assignment(t, g["slot"], crew, [x for x in groups if x is not other], staff)
    assert errs
    r = agents.reconcile(agent_says_ok=True, validator_errors=errs)
    assert r == {"ok": False, "disagreement": True}


def test_notification_draft_mentions_ticket_and_emergency_rule(world):
    df, staff, groups, by_id, tickets = world
    g = groups[0]
    txt = agents.notification_draft(tickets[g["ticket_id"]], g["slot"], {"Mechanic": "A"}, urgent=True)
    assert g["ticket_id"] in txt and txt.startswith("URGENT") and "911" in txt
