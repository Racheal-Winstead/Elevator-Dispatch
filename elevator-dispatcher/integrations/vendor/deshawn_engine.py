"""Elevator Dispatcher -- scheduling logic (no UI code in this file).

Everything the dispatcher screen needs to decide lives here:
loading + checking tickets, triage, crew eligibility, the ONE rule-checker
(validate_assignment) used by both auto-schedule and manual changes, and
reason codes for work that can't be staffed.

All rules and numbers here are DEMO-CONFIGURED, not NYCHA policy.
"""
from __future__ import annotations

import itertools
import re
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
RULE_VERSION = "demo-rules-v0.1"

# A fixed "now" so the demo looks the same every time it is run.
DEMO_NOW = pd.Timestamp("2026-11-05 08:00")

# The four fixed demo time slots (PRD: "four fixed slots", illustrative only).
SLOTS = {
    "S1": ("08:00", "10:00"),
    "S2": ("10:00", "12:00"),
    "S3": ("13:00", "15:00"),
    "S4": ("15:00", "17:00"),
}

# Which roles a job needs, by work type. DEMO-CONFIGURED: NYCHA must confirm real crew rules.
CREW_RULES = {
    "Elevator outage": ["Mechanic", "Helper"],
    "Degraded operation": ["Mechanic", "Helper"],
    "Door fault": ["Mechanic", "Helper"],
    "Planned maintenance": ["Mechanic"],
}

REQUIRED_TICKET_FIELDS = [
    "ticket_id", "reported_at", "work_type", "description",
    "development", "building", "borough", "source_priority",
]

TRIAGE_LABELS = {
    1: "T1 Immediate hazard",
    2: "T2 Critical service impact",
    3: "T3 Standard outage",
    4: "T4 Degraded operation",
    5: "T5 Planned maintenance",
}

STATUSES = ["UNASSIGNED", "ASSIGNED", "ACKNOWLEDGED", "EN_ROUTE", "ON_SITE", "BLOCKED", "RESTORED", "CLOSED"]

REASON_HELP = {
    "INVALID_TICKET_DATA": "Required field missing or malformed. Held in review, not scheduled.",
    "UNKNOWN_WORK_TYPE": "Work type is not in the approved list. Held in review.",
    "POSSIBLE_DUPLICATE": "May be a repeat of another ticket on the same elevator. Flagged only; nothing is merged.",
    "HAZARD_REVIEW_REQUIRED": "Wording suggests a hazard but the source did not confirm it. Dispatcher must decide.",
    "TECH_ABSENT": "Person is absent, inactive or unavailable.",
    "ATTENDANCE_UNKNOWN": "Attendance is unknown, so the person is NOT treated as available.",
    "NO_QUALIFIED_CREW": "No one with a valid certification and the right role is available.",
    "SECTOR_OR_DEPOT_MISMATCH": "No one is authorized for this borough.",
    "OFF_SHIFT": "Everyone eligible is off shift for the time slots.",
    "NO_CAPACITY": "Eligible people exist, but every time slot is already booked.",
    "CREW_UNAVAILABLE": "Both roles have free time, but never in the same slot.",
    "DOUBLE_BOOKED": "Someone is already booked in that slot.",
    "EMERGENCY_ESCALATION_REQUIRED": "Urgent case could not be staffed. A human must act.",
    "MANUAL_CONFLICT": "That manual change breaks a hard rule. Nothing was changed.",
    "MESSAGE_BLOCKED_CONFLICT": "Recipient has an overlapping assignment. Send blocked unless the dispatcher confirms an urgent send.",
    "MESSAGE_BLOCKED_OFF_DUTY": "Recipient is not present or is outside shift. Send blocked.",
    "NO_ACK": "No acknowledgement within the time limit. Dispatcher must follow up.",
    "EXISTING_COMMITMENT_UNKNOWN": "Bookings outside this tool were not loaded, so conflicts with them are not checked.",
}

HAZARD_WORDS = re.compile(
    r"stuck|trapped|entrap|fire|smoke|injur|accident|open hatch|shaft|fell|fall", re.I
)


# ----------------------------------------------------------------------------
# Loading and checking tickets
# ----------------------------------------------------------------------------
def load_tickets(path: Path | None = None, raw: pd.DataFrame | None = None):
    """Read tickets.csv (or take an already-mapped `raw` frame, e.g. from the
    Maximo adapter), check each row, and return (DataFrame, info dict).

    Bad rows are KEPT and marked, never silently dropped. An exact repeat of a
    ticket_id keeps the last copy and the dropped IDs are reported in `info`.
    """
    if raw is None:
        path = path or BASE / "tickets.csv"
        raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    raw = raw.apply(lambda c: c.str.strip())
    info = {"rows_read": len(raw), "duplicate_ids_dropped": []}

    has_id = raw["ticket_id"] != ""
    dup = has_id & raw.duplicated("ticket_id", keep="last")
    info["duplicate_ids_dropped"] = raw.loc[dup, "ticket_id"].tolist()
    df = raw.loc[~dup].reset_index(drop=True)

    issues, status = [], []
    for i, r in df.iterrows():
        problems = [f for f in REQUIRED_TICKET_FIELDS if r[f] == ""]
        if r["reported_at"] and pd.isna(pd.to_datetime(r["reported_at"], errors="coerce")):
            problems.append("reported_at (bad format)")
        if r["source_priority"] and r["source_priority"] not in {"1", "2", "3", "4", "5"}:
            problems.append("source_priority (must be 1-5)")
        if problems:
            issues.append("Missing/invalid: " + ", ".join(problems))
            status.append("INVALID_TICKET_DATA")
        elif r["work_type"] not in CREW_RULES:
            issues.append(f"Work type '{r['work_type']}' not recognised")
            status.append("UNKNOWN_WORK_TYPE")
        else:
            issues.append("")
            status.append("OK")
    df["data_status"] = status
    df["issues"] = issues
    # Give blank IDs a visible placeholder so they can still be listed.
    df["ticket_id"] = [
        t if t else f"NO-ID-ROW-{i + 2}" for i, t in enumerate(df["ticket_id"])
    ]
    df["reported_dt"] = pd.to_datetime(df["reported_at"], errors="coerce")
    df["priority_num"] = pd.to_numeric(df["source_priority"], errors="coerce")

    # Possible duplicates: same elevator, different ticket, reported within 24h.
    dup_of = {t: [] for t in df["ticket_id"]}
    ok = df[(df["data_status"] == "OK") & (df["elevator_asset_id"] != "")]
    for a, b in itertools.combinations(ok.index, 2):
        ra, rb = ok.loc[a], ok.loc[b]
        if ra["elevator_asset_id"] == rb["elevator_asset_id"] and (
            abs(ra["reported_dt"] - rb["reported_dt"]) <= pd.Timedelta(hours=24)
        ):
            dup_of[ra["ticket_id"]].append(rb["ticket_id"])
            dup_of[rb["ticket_id"]].append(ra["ticket_id"])
    df["possible_dup_of"] = [", ".join(dup_of[t]) for t in df["ticket_id"]]

    df["hazard_keyword"] = [
        bool(HAZARD_WORDS.search(d)) and h != "Y"
        for d, h in zip(df["description"], df["hazard_confirmed"])
    ]
    return df, info


def load_tickets_from_maximo(payload: dict):
    """Ingest a Maximo-shaped payload through the SAME checks as the CSV path.

    Missing/blank fields become INVALID_TICKET_DATA via load_tickets. Maximo's own
    status is kept read-only in `maximo_status`; it never touches dispatcher statuses.
    """
    import maximo_mock
    # `maximo_status` rides along as an extra column (read-only source data).
    return load_tickets(raw=maximo_mock.from_maximo(payload))


def load_staff(path: Path | None = None) -> list[dict]:
    path = path or BASE / "staff.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False).apply(lambda c: c.str.strip())
    staff = df.to_dict("records")
    for t in staff:
        t["boroughs"] = [b for b in t["authorized_boroughs"].split("|") if b]
    return staff


# ----------------------------------------------------------------------------
# Triage and ordering
# ----------------------------------------------------------------------------
def triage_for(t: dict, confirmed: set[str]) -> tuple[int, str]:
    """Return (triage level 1-5, plain-English reason). Never guesses from keywords."""
    if t["hazard_confirmed"] == "Y":
        return 1, "Source confirms a hazard"
    if t["ticket_id"] in confirmed:
        return 1, "Dispatcher confirmed hazard"
    if t["no_service"] == "Y":
        return 2, "Source says no service" + (" (senior building)" if t["senior_building"] == "Y" else "")
    if t["work_type"] == "Planned maintenance":
        return 5, "Planned maintenance"
    if t["work_type"] == "Degraded operation":
        return 4, "Degraded operation"
    return 3, "Standard outage / fault"


def with_triage(df: pd.DataFrame, confirmed: set[str]) -> pd.DataFrame:
    out = df.copy()
    res = [triage_for(r, confirmed) for r in out.to_dict("records")]
    out["triage"] = [r[0] for r in res]
    out["triage_why"] = [f"{r[1]} [{RULE_VERSION}]" for r in res]
    out["triage_label"] = out["triage"].map(TRIAGE_LABELS)
    return out


def priority_order(df: pd.DataFrame) -> pd.DataFrame:
    """Fixed, repeatable order: hazard, critical impact, then source priority,
    oldest first, then ticket ID as the final tie-break."""
    d = df.copy()
    d["_band"] = d["triage"].clip(upper=3)
    d = d.sort_values(["_band", "priority_num", "reported_dt", "ticket_id"], kind="stable")
    return d.drop(columns="_band")


# ----------------------------------------------------------------------------
# Crew eligibility
# ----------------------------------------------------------------------------
def tech_block(t: dict, borough: str | None = None):
    """None if this person can be scheduled, else (reason_code, short detail)."""
    if borough is not None and borough not in t["boroughs"]:
        return "SECTOR_OR_DEPOT_MISMATCH", f"not authorized for {borough}"
    if t["active"] != "Y":
        return "TECH_ABSENT", "inactive"
    att = t["attendance_state"]
    if att == "UNKNOWN":
        return "ATTENDANCE_UNKNOWN", "attendance unknown (not treated as available)"
    if att != "PRESENT":
        return "TECH_ABSENT", att.lower().replace("_", " ")
    expiry = t["certification_expiry"]
    if t["certification_status"] == "EXPIRED" or (
        expiry and pd.Timestamp(expiry) < DEMO_NOW.normalize()
    ):
        return "NO_QUALIFIED_CREW", "certification expired"
    return None


def in_shift(t: dict, slot: str) -> bool:
    start, end = SLOTS[slot]
    return t["shift_start"] <= start and end <= t["shift_end"]


def is_busy(tech_id: str, slot: str, assignments: list[dict], exclude_group=None) -> str | None:
    """Ticket ID the person is already booked on in this slot, else None."""
    for g in assignments:
        if g["group_id"] == exclude_group:
            continue
        if g["slot"] == slot and tech_id in g["crew"].values():
            return g["ticket_id"]
    return None


def validate_assignment(ticket, slot, crew, assignments, staff, exclude_group=None):
    """THE hard-rule checker. Auto-schedule and manual changes both go through it.

    Returns a list of (reason_code, message). Empty list = allowed.
    """
    errs = []
    if ticket["data_status"] != "OK":
        return [("INVALID_TICKET_DATA", "Ticket has data problems and cannot be scheduled")]
    roles = CREW_RULES[ticket["work_type"]]
    by_id = {t["tech_id"]: t for t in staff}

    for role in roles:
        if not crew.get(role):
            errs.append(("CREW_UNAVAILABLE", f"{role} is required but not chosen"))
    for role, tid in crew.items():
        if tid and role not in roles:
            errs.append(("MANUAL_CONFLICT", f"{role} is not required for {ticket['work_type']}"))
    ids = [v for v in crew.values() if v]
    if len(set(ids)) < len(ids):
        errs.append(("MANUAL_CONFLICT", "The same person cannot fill two roles"))
    for g in assignments:
        if g["group_id"] != exclude_group and g["ticket_id"] == ticket["ticket_id"]:
            errs.append(("MANUAL_CONFLICT", "This ticket already has a crew"))

    start, end = SLOTS[slot]
    for role, tid in crew.items():
        if not tid:
            continue
        t = by_id.get(tid)
        if t is None:
            errs.append(("MANUAL_CONFLICT", f"Unknown person {tid}"))
            continue
        if t["role"] != role:
            errs.append(("NO_QUALIFIED_CREW", f"{t['name']} is a {t['role']}, not a {role}"))
            continue
        blk = tech_block(t, ticket["borough"])
        if blk:
            errs.append((blk[0], f"{t['name']}: {blk[1]}"))
        if not in_shift(t, slot):
            errs.append(("OFF_SHIFT", f"{t['name']} works {t['shift_start']}-{t['shift_end']}, slot {slot} is {start}-{end}"))
        other = is_busy(tid, slot, assignments, exclude_group)
        if other:
            errs.append(("DOUBLE_BOOKED", f"{t['name']} is already on {other} in {slot}"))
    return errs


def _candidates(role, ticket, slot, assignments, staff):
    pool = [
        t for t in staff
        if t["role"] == role
        and tech_block(t, ticket["borough"]) is None
        and in_shift(t, slot)
        and not is_busy(t["tech_id"], slot, assignments)
    ]
    # Local people first, float helper only when needed; ID order keeps it repeatable.
    return sorted(pool, key=lambda t: (t["float_helper"] == "Y", t["tech_id"]))


def explain_unassigned(ticket, assignments, staff) -> list[tuple[str, str]]:
    """Why couldn't this ticket be staffed? Returns (code, detail) pairs."""
    reasons = []
    free_slots = {}
    for role in CREW_RULES[ticket["work_type"]]:
        pool = [t for t in staff if t["role"] == role]
        auth = [t for t in pool if ticket["borough"] in t["boroughs"]]
        if not auth:
            reasons.append(("SECTOR_OR_DEPOT_MISMATCH", f"No {role} is authorized for {ticket['borough']}"))
            continue
        usable, blocked = [], []
        for t in auth:
            blk = tech_block(t, ticket["borough"])
            if blk:
                blocked.append((blk[0], f"{t['name']}: {blk[1]}"))
            else:
                usable.append(t)
        if not usable:
            # Only mention individual blocks when nobody in this role can work.
            reasons.extend(blocked)
            reasons.append(("NO_QUALIFIED_CREW", f"No schedulable {role} for {ticket['borough']}"))
            continue
        shift_ok = [s for s in SLOTS if any(in_shift(t, s) for t in usable)]
        if not shift_ok:
            reasons.append(("OFF_SHIFT", f"No eligible {role} is on shift during any slot"))
            continue
        free_slots[role] = {
            s for s in shift_ok
            if any(in_shift(t, s) and not is_busy(t["tech_id"], s, assignments) for t in usable)
        }
    if not reasons:
        roles = CREW_RULES[ticket["work_type"]]
        if any(not free_slots.get(r) for r in roles):
            reasons.append(("NO_CAPACITY", "All eligible people are booked in every slot"))
        else:
            common = set.intersection(*(free_slots[r] for r in roles))
            if not common:
                reasons.append(("CREW_UNAVAILABLE", "No slot where a full crew is free together"))
    if ticket["triage"] == 1:
        reasons.append(("EMERGENCY_ESCALATION_REQUIRED", "Urgent case is unstaffed; human escalation needed"))
    seen, out = set(), []
    for code, detail in reasons:  # keep the first detail per code
        if code not in seen:
            seen.add(code)
            out.append((code, detail))
    return out


def auto_schedule(tickets: pd.DataFrame, staff, assignments, start_id: int = 1):
    """Staff every OK, not-yet-assigned ticket where a full valid crew exists.

    Tickets go in priority order; each takes the earliest slot with a valid
    crew. Nothing is forced: if no valid crew exists the ticket stays unassigned.
    Existing assignments are never touched. Returns the NEW groups only.
    """
    work = list(assignments)
    new = []
    counter = itertools.count(start_id)
    already = {g["ticket_id"] for g in work}
    sched = priority_order(tickets[tickets["data_status"] == "OK"])
    for t in sched.to_dict("records"):
        if t["ticket_id"] in already:
            continue
        for slot in SLOTS:
            crew = {}
            for role in CREW_RULES[t["work_type"]]:
                c = _candidates(role, t, slot, work, staff)
                if not c:
                    break
                crew[role] = c[0]["tech_id"]
            else:
                if not validate_assignment(t, slot, crew, work, staff):
                    g = {
                        "group_id": f"G-{next(counter):03d}",
                        "ticket_id": t["ticket_id"],
                        "slot": slot,
                        "crew": crew,
                        "source": "AUTO",
                        "rule_version": RULE_VERSION,
                    }
                    work.append(g)
                    new.append(g)
                    break
    return new


def integrity_violations(assignments, tickets: pd.DataFrame, staff) -> int:
    """Re-check every committed assignment against the hard rules. Should be 0."""
    by_ticket = {r["ticket_id"]: r for r in tickets.to_dict("records")}
    n = 0
    for g in assignments:
        n += len(validate_assignment(by_ticket[g["ticket_id"]], g["slot"], g["crew"], assignments, staff, exclude_group=g["group_id"]))
    return n
