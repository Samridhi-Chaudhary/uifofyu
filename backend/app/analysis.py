"""Pure analysis functions (no I/O) so they are easy to unit test."""
import numpy as np
import pandas as pd

TZ = "Europe/London"


def delivery_days(start, end):
    """Decisions on day D-1 for delivery day D."""
    return [d.date() for d in pd.date_range(pd.Timestamp(start) + pd.Timedelta(days=1),
                                            pd.Timestamp(end) + pd.Timedelta(days=1))]


def snapshot(fc, day, cutoff_hour):
    """Latest forecast per target time that was published at/before the D-1 cutoff."""
    d = pd.Timestamp(day)
    start = d.tz_localize(TZ)
    end = (d + pd.Timedelta(days=1)).tz_localize(TZ)
    cutoff = (d - pd.Timedelta(days=1)).tz_localize(TZ) + pd.Timedelta(hours=cutoff_hour)
    s = fc[(fc.publishTime <= cutoff) & (fc.startTime >= start) & (fc.startTime < end)]
    s = s.sort_values("publishTime").groupby("startTime", as_index=False).last()
    return s, cutoff


def metrics(df):
    """error = forecast - actual. Positive => forecast overstated wind (shortfall risk)."""
    if df.empty:
        return {"n": 0}
    e = df["forecast"] - df["actual"]
    nz = df["actual"] > 0
    q = e.quantile([.05, .5, .95])
    return {"n": int(len(df)), "mae": e.abs().mean(), "rmse": float(np.sqrt((e ** 2).mean())),
            "bias": e.mean(), "mape": (e[nz].abs() / df.loc[nz, "actual"]).mean() * 100,
            "p05": q[.05], "p50": q[.5], "p95": q[.95], "p95_abs": e.abs().quantile(.95),
            "mean_actual": df["actual"].mean()}


def decision_frame(fc, act, days, cutoff_hour):
    parts = []
    for d in days:
        s, _ = snapshot(fc, d, cutoff_hour)
        if s.empty:
            continue
        s = s.merge(act, on="startTime", how="inner")
        s["day"] = str(d)
        parts.append(s)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["startTime", "publishTime", "forecast", "actual", "day"])


def lead_comparison(fc, act, days, cutoff_hour, lead=4):
    """Decision-time (D-1) forecast vs the latest forecast published >= `lead` h before target."""
    dec = decision_frame(fc, act, days, cutoff_hour)
    m = fc.merge(act, on="startTime", how="inner")
    m["lead_h"] = (m.startTime - m.publishTime).dt.total_seconds() / 3600
    m = m[m.lead_h >= lead].sort_values("publishTime").groupby("startTime", as_index=False).last()
    c = dec[["startTime", "forecast", "actual"]].merge(m[["startTime", "forecast"]], on="startTime", suffixes=("", "_s"))
    later = c[["forecast_s", "actual"]].rename(columns={"forecast_s": "forecast"})
    return {"decision": metrics(c[["forecast", "actual"]]), "later": metrics(later), "lead_h": lead}


def accuracy(fc, act, days, cutoff_hour):
    df = decision_frame(fc, act, days, cutoff_hour)
    df["hour"] = df["startTime"].dt.tz_convert(TZ).dt.hour
    daily = [{"day": d, **metrics(g)} for d, g in df.groupby("day")]
    hourly = [{"hour": int(h), **metrics(g)} for h, g in df.groupby("hour")]
    # all published forecasts, by lead time (how does error grow with horizon?)
    m = fc.merge(act, on="startTime", how="inner")
    m["lead_h"] = (m.startTime - m.publishTime).dt.total_seconds() / 3600
    m = m[m.lead_h >= 0]
    m["bucket"] = (np.minimum(m.lead_h // 6 * 6, 42)).astype(int)
    horizon = [{"lead_from_h": int(b), "lead_to_h": int(b) + 6 if b < 42 else None, **metrics(g)}
               for b, g in m.groupby("bucket")]
    worst = sorted([d for d in daily if d.get("n")], key=lambda d: -d["mae"])[:5]
    return {"overall": metrics(df), "daily": daily, "hourly": hourly, "horizon": horizon,
            "worst_days": worst, "compare": lead_comparison(fc, act, days, cutoff_hour)}


def forecast_view(fc, act, day, cutoff_hour, all_days, pct=0.95):
    s, cutoff = snapshot(fc, day, cutoff_hour)
    prior = [d for d in all_days if d < day]  # no look-ahead: only past errors
    hist = decision_frame(fc, act, prior, cutoff_hour)
    hm = metrics(hist)
    buffer = float((hist.forecast - hist.actual).quantile(pct)) if hm.get("n") else None  # pct-quantile over-forecast
    v = s.merge(act, on="startTime", how="left")
    if buffer is not None:
        v["conservative"] = (v.forecast - max(buffer, 0)).clip(lower=0)
    d0 = pd.Timestamp(day)
    st, en = d0.tz_localize(TZ), (d0 + pd.Timedelta(days=1)).tz_localize(TZ)
    seen = fc[(fc.publishTime <= cutoff) & (fc.startTime >= st) & (fc.startTime < en)]
    age = (cutoff - s.publishTime.max()).total_seconds() / 3600 if len(s) else None
    summary = {"cutoff": cutoff.tz_convert("UTC").isoformat(), "n_points": int(len(s)),
               "n_revisions": int(seen.publishTime.nunique()), "age_h": age,
               "latest_publish": s.publishTime.max().isoformat() if len(s) else None,
               "avg_mw": s.forecast.mean() if len(s) else None,
               "min_mw": s.forecast.min() if len(s) else None,
               "max_mw": s.forecast.max() if len(s) else None,
               "history_days": len(prior), "history": hm, "buffer_mw": buffer}
    return v, summary
