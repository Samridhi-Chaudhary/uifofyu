"""Live checks against the real Elexon API.  Run:  RUN_LIVE=1 python -m pytest tests/test_live_api.py -v
(PowerShell:  $env:RUN_LIVE="1"; python -m pytest tests/test_live_api.py -v)"""
import os
import httpx
import pytest
from app import data

pytestmark = pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="set RUN_LIVE=1 to hit Elexon")


def test_actuals_one_full_day_is_48_half_hours():
    with httpx.Client() as c:
        rows = data._get(c, "FUELHH", {"settlementDateFrom": "2026-01-05", "settlementDateTo": "2026-01-05", "fuelType": "WIND"})
    assert len(rows) == 48
    assert {"startTime", "generation", "fuelType"} <= set(rows[0])
    assert all(r["fuelType"] == "WIND" for r in rows)


def test_forecast_has_required_fields_and_lead_times():
    with httpx.Client() as c:
        rows = data._get(c, "WINDFOR", {"publishDateTimeFrom": "2026-01-05T00:00:00Z", "publishDateTimeTo": "2026-01-06T00:00:00Z"})
    assert rows and {"startTime", "publishTime", "generation"} <= set(rows[0])


def test_full_pipeline_data_is_clean():
    d = data.load(force=True)  # fresh download, ignores cache
    a, f = d["actuals"], d["forecasts"]
    assert len(a) == 32 * 48 and a.actual.isna().sum() == 0
    # WINDFOR contains some rows for hours BEFORE their publish time; they must be a minority.
    lead_h = (f.startTime - f.publishTime).dt.total_seconds() / 3600
    assert (lead_h >= 0).mean() > 0.5
    # No decision-time snapshot may ever contain a forecast published after its cutoff.
    from app import analysis
    for day in analysis.delivery_days(data.DECISION_START, data.DECISION_END):
        snap, cutoff = analysis.snapshot(f, day, 9)
        assert snap.empty or snap.publishTime.max() <= cutoff