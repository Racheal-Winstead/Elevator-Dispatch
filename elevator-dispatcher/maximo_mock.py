"""Local MOCK of a Maximo work-order feed (DEMO). No network, no credentials.

FIELD NAMES ARE UNVERIFIED FOR NYCHA. wonum, siteid, description, wopriority,
assetnum, location, status, reportdate and worktype are common Maximo
(MXWO) names, but NYCHA's real object structure, site IDs and status values
have not been confirmed. Fields prefixed `x_` are invented here to carry demo
columns Maximo-shaped data would not hold; they are NOT Maximo fields.

Maximo `status` is read-only source data. It is kept in the `maximo_status`
column and is never mixed with dispatcher statuses (engine.STATUSES).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent

# ticket column -> mock Maximo field (UNVERIFIED)
FIELD_MAP = {
    "ticket_id": "wonum",
    "development": "siteid",
    "description": "description",
    "source_priority": "wopriority",
    "elevator_asset_id": "assetnum",
    "building": "location",
    "reported_at": "reportdate",
    "work_type": "worktype",
    "source_record_id": "x_source_record_id",
    "borough": "x_borough",
    "no_service": "x_no_service",
    "senior_building": "x_senior_building",
    "hazard_confirmed": "x_hazard_confirmed",
}
MAXIMO_STATUS = "WAPPR"  # demo value only; real NYCHA statuses unverified


def to_maximo(path: Path | None = None) -> dict:
    """tickets.csv -> {"member": [ ... ]} Maximo-shaped JSON (as a dict)."""
    raw = pd.read_csv(path or BASE / "tickets.csv", dtype=str, keep_default_na=False)
    members = []
    for r in raw.to_dict("records"):
        m = {mx: r[col] for col, mx in FIELD_MAP.items()}
        m["status"] = MAXIMO_STATUS
        members.append(m)
    return {"member": members}


def from_maximo(payload: dict) -> pd.DataFrame:
    """Maximo-shaped payload -> frame with the existing ticket columns.

    A missing key becomes a blank string, so engine.load_tickets flags the row
    INVALID_TICKET_DATA instead of crashing or silently dropping it.
    """
    rows = []
    for m in payload.get("member", []):
        row = {col: str(m.get(mx) if m.get(mx) is not None else "") for col, mx in FIELD_MAP.items()}
        row["maximo_status"] = str(m.get("status") or "")
        rows.append(row)
    cols = list(FIELD_MAP) + ["maximo_status"]
    return pd.DataFrame(rows, columns=cols, dtype=str)
