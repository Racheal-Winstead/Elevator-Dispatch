"""Run with:  python -m pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import engine as eng  # noqa: E402


def setup():
    df, info = eng.load_tickets()
    return eng.with_triage(df, set()), info, eng.load_staff()


def test_bad_data_is_kept_not_dropped():
    df, info, _ = setup()
    bad = df[df.data_status != "OK"]
    assert len(bad) == 2                       # missing borough, missing ticket id
    assert info["duplicate_ids_dropped"] == ["T-1011"]
    assert df.ticket_id.is_unique


def test_no_rule_violations_and_deterministic():
    df, _, staff = setup()
    a = eng.auto_schedule(df, staff, [])
    b = eng.auto_schedule(df, staff, [])
    assert a == b
    assert eng.integrity_violations(a, df, staff) == 0
    assert all(t not in {g["ticket_id"] for g in a} for t in df[df.data_status != "OK"].ticket_id)


def test_pairs_are_complete():
    df, _, staff = setup()
    by = df.set_index("ticket_id")
    for g in eng.auto_schedule(df, staff, []):
        assert set(g["crew"]) == set(eng.CREW_RULES[by.loc[g["ticket_id"], "work_type"]])


def test_no_double_booking():
    df, _, staff = setup()
    seen = set()
    for g in eng.auto_schedule(df, staff, []):
        for tid in g["crew"].values():
            assert (tid, g["slot"]) not in seen
            seen.add((tid, g["slot"]))


def test_manual_double_booking_rejected():
    df, _, staff = setup()
    groups = eng.auto_schedule(df, staff, [])
    g = groups[0]
    free = df[(df.data_status == "OK") & ~df.ticket_id.isin([x["ticket_id"] for x in groups])].iloc[0].to_dict()
    errs = eng.validate_assignment(free, g["slot"], dict(g["crew"]), groups, staff)
    assert any(c == "DOUBLE_BOOKED" for c, _ in errs)


def test_unknown_expired_absent_never_scheduled():
    df, _, staff = setup()
    used = {i for g in eng.auto_schedule(df, staff, []) for i in g["crew"].values()}
    assert not used & {"M5", "H5", "H3"}       # absent, unknown attendance, expired cert


def test_unstaffed_emergency_gets_reason_not_forced():
    df, _, staff = setup()
    groups = eng.auto_schedule(df, staff, [])
    t = df[df.ticket_id == "T-1021"].iloc[0].to_dict()
    assert t["ticket_id"] not in {g["ticket_id"] for g in groups}
    codes = [c for c, _ in eng.explain_unassigned(t, groups, staff)]
    assert "EMERGENCY_ESCALATION_REQUIRED" in codes


def test_keyword_alone_is_not_an_emergency():
    df, _, _ = setup()
    r = df[df.ticket_id == "T-1006"].iloc[0]
    assert r.hazard_keyword and r.triage != 1


def test_every_unassigned_valid_ticket_has_a_reason():
    df, _, staff = setup()
    groups = eng.auto_schedule(df, staff, [])
    done = {g["ticket_id"] for g in groups}
    for t in df[(df.data_status == "OK") & ~df.ticket_id.isin(done)].to_dict("records"):
        assert eng.explain_unassigned(t, groups, staff)


def test_speed_target():
    import time
    df, _, staff = setup()
    t0 = time.perf_counter()
    eng.auto_schedule(df, staff, [])
    assert time.perf_counter() - t0 < 5
