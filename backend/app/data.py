"""Elexon BMRS data access (FUELHH actuals + WINDFOR forecasts) with disk cache."""
import datetime as dt
import os
import tempfile
import pandas as pd
import httpx

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
CACHE = os.environ.get("CACHE_FILE", os.path.join(tempfile.gettempdir(), "elexon_cache.pkl"))
DECISION_START = dt.date(2026, 1, 1)   # purchase decisions made in Jan 2026
DECISION_END = dt.date(2026, 1, 31)    # -> delivery days 2 Jan .. 1 Feb


def _get(client, path, params):
    r = client.get(f"{BASE}/{path}/stream", params=params, timeout=90)
    r.raise_for_status()
    j = r.json()
    return j if isinstance(j, list) else j.get("data", [])


def _chunks(start, end, days):
    cur = start
    while cur <= end:
        nxt = min(cur + dt.timedelta(days=days - 1), end)
        yield cur, nxt
        cur = nxt + dt.timedelta(days=1)


def fetch_actuals(client):
    rows = []
    for a, b in _chunks(DECISION_START, DECISION_END + dt.timedelta(days=1), 7):
        rows += _get(client, "FUELHH", {"settlementDateFrom": a.isoformat(),
                                        "settlementDateTo": b.isoformat(),
                                        "fuelType": "WIND"})
    df = pd.DataFrame(rows)
    df = df[df["fuelType"] == "WIND"]
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    return (df[["startTime", "generation"]].rename(columns={"generation": "actual"})
            .drop_duplicates("startTime").sort_values("startTime").reset_index(drop=True))


def fetch_forecasts(client):
    rows = []
    for a, b in _chunks(DECISION_START, DECISION_END, 3):
        rows += _get(client, "WINDFOR", {
            "publishDateTimeFrom": f"{a.isoformat()}T00:00:00Z",
            "publishDateTimeTo": f"{(b + dt.timedelta(days=1)).isoformat()}T00:00:00Z"})
    df = pd.DataFrame(rows)
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    return (df[["startTime", "publishTime", "generation"]].rename(columns={"generation": "forecast"})
            .drop_duplicates(["startTime", "publishTime"]).reset_index(drop=True))


def load(force=False):
    if not force and os.path.exists(CACHE):
        return pd.read_pickle(CACHE)
    with httpx.Client() as c:
        out = {"actuals": fetch_actuals(c), "forecasts": fetch_forecasts(c)}
    pd.to_pickle(out, CACHE)
    return out
