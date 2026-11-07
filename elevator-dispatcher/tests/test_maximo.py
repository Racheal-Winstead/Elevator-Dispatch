"""Maximo mock + adapter."""
import copy

import engine as eng
import maximo_mock as mm


def test_shape():
    p = mm.to_maximo()
    assert list(p) == ["member"]
    for f in ("wonum", "siteid", "description", "wopriority", "assetnum", "location", "status"):
        assert f in p["member"][0]


def test_round_trip_matches_csv():
    csv_df, _ = eng.load_tickets()
    mx_df, _ = eng.load_tickets_from_maximo(mm.to_maximo())
    cols = [c for c in csv_df.columns]
    assert csv_df[cols].equals(mx_df[cols])


def test_missing_fields_become_invalid_ticket_data():
    p = copy.deepcopy(mm.to_maximo())
    del p["member"][2]["description"]
    p["member"][3]["siteid"] = ""
    df, _ = eng.load_tickets_from_maximo(p)
    st = dict(zip(df["ticket_id"], df["data_status"]))
    t2, t3 = p["member"][2]["wonum"], p["member"][3]["wonum"]
    assert st[t2] == "INVALID_TICKET_DATA" and st[t3] == "INVALID_TICKET_DATA"


def test_maximo_status_is_separate():
    df, _ = eng.load_tickets_from_maximo(mm.to_maximo())
    assert set(df["maximo_status"]) == {mm.MAXIMO_STATUS}
    assert mm.MAXIMO_STATUS not in eng.STATUSES
