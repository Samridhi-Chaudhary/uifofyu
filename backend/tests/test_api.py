import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app import main


@pytest.fixture()
def client():
    t = pd.date_range("2026-01-01", periods=48 * 33, freq="30min", tz="UTC")
    act = pd.DataFrame({"startTime": t, "actual": 1000 + 200 * np.sin(np.arange(len(t)) / 20)})
    rows = []
    for p in pd.date_range("2026-01-01", periods=31 * 8, freq="3h", tz="UTC"):
        tt = t[(t >= p) & (t < p + pd.Timedelta(hours=48))][::2]
        rows.append(pd.DataFrame({"startTime": tt, "publishTime": p, "forecast": 1050 + 200 * np.sin(np.searchsorted(t, tt) / 20)}))
    main._state["data"] = {"actuals": act, "forecasts": pd.concat(rows, ignore_index=True)}
    yield TestClient(main.app)
    main._state["data"] = None


def test_health_and_days(client):
    assert client.get("/api/health").json()["ready"] is True
    assert len(client.get("/api/days").json()) == 31


def test_forecast_endpoint(client):
    j = client.get("/api/forecast?date=2026-01-15&cutoff_hour=9").json()
    assert j["summary"]["n_revisions"] > 0 and j["summary"]["age_h"] >= 0 and len(j["series"]) > 0


def test_forecast_rejects_non_january_decision_day(client):
    assert client.get("/api/forecast?date=2026-03-01").status_code == 400


def test_accuracy_shape(client):
    j = client.get("/api/accuracy").json()
    assert {"overall", "daily", "hourly", "horizon", "worst_days", "compare"} <= set(j)
    assert abs(j["overall"]["bias"] - 50) < 1e-6  # synthetic forecast is exactly +50 MW too high


def test_data_quality_and_csv(client):
    q = client.get("/api/data-quality").json()
    assert q["cutoff_violations"] == 0 and q["late_rows"] == 0
    assert client.get("/api/forecast.csv?date=2026-01-15").headers["content-type"].startswith("text/csv")
