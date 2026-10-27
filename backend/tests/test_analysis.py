import pandas as pd
from app import analysis


def make():
    t = pd.date_range("2026-01-02", periods=48, freq="h", tz="UTC")
    act = pd.DataFrame({"startTime": t, "actual": 1000.0})
    old = pd.DataFrame({"startTime": t, "publishTime": pd.Timestamp("2026-01-01 06:00", tz="UTC"), "forecast": 1100.0})
    late = pd.DataFrame({"startTime": t, "publishTime": pd.Timestamp("2026-01-01 15:00", tz="UTC"), "forecast": 900.0})
    return act, pd.concat([old, late], ignore_index=True)


def test_snapshot_excludes_forecasts_after_cutoff():
    _, fc = make()
    s, _ = analysis.snapshot(fc, pd.Timestamp("2026-01-02").date(), 9)
    assert len(s) == 24 and (s.forecast == 1100).all()


def test_metrics_sign_and_values():
    act, fc = make()
    df = analysis.decision_frame(fc, act, [pd.Timestamp("2026-01-02").date()], 9)
    m = analysis.metrics(df)
    assert m["mae"] == 100 and m["bias"] == 100 and abs(m["mape"] - 10) < 1e-9


def test_lead_comparison_and_pct():
    act, fc = make()
    days = [pd.Timestamp("2026-01-02").date()]
    c = analysis.lead_comparison(fc, act, days, 9, lead=4)
    assert c["decision"]["mae"] == 100 and c["later"]["mae"] == 100


def test_forecast_view_counts_revisions_and_age():
    act, fc = make()
    day = pd.Timestamp("2026-01-02").date()
    _, s9 = analysis.forecast_view(fc, act, day, 9, [day])
    _, s18 = analysis.forecast_view(fc, act, day, 18, [day])
    assert s9["n_revisions"] == 1 and s18["n_revisions"] == 2 and abs(s9["age_h"] - 3) < 1e-9
