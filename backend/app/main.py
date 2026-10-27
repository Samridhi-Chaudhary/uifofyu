import datetime as dt
import math
import os
import threading
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import analysis, data

_state = {"data": None, "error": None}
_lock = threading.Lock()


def _ensure():
    with _lock:
        if _state["data"] is None:
            try:
                _state["data"], _state["error"] = data.load(), None
            except Exception as e:  # surfaced via /api/health
                _state["error"] = str(e)
                raise HTTPException(503, f"Data load failed: {e}")
    return _state["data"]


@asynccontextmanager
async def lifespan(app):
    def warm():
        try:
            _ensure()
        except Exception:
            pass
    threading.Thread(target=warm, daemon=True).start()
    yield


app = FastAPI(title="Wind Forecast Analyser", lifespan=lifespan)
DAYS = analysis.delivery_days(data.DECISION_START, data.DECISION_END)


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, pd.Timestamp):
        return o.tz_convert("UTC").isoformat()
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if hasattr(o, "item"):
        return clean(o.item())
    return o


@app.get("/api/health")
def health():
    return {"ready": _state["data"] is not None, "error": _state["error"]}


@app.get("/api/days")
def days():
    return [str(d) for d in DAYS]


@app.get("/api/forecast")
def forecast(date: dt.date, cutoff_hour: int = Query(9, ge=0, le=23), percentile: float = Query(0.95, ge=0.5, le=0.99)):
    if date not in DAYS:
        raise HTTPException(400, "date must be a delivery day for January 2026 decisions")
    d = _ensure()
    v, summary = analysis.forecast_view(d["forecasts"], d["actuals"], date, cutoff_hour, DAYS, percentile)
    return clean({"summary": summary, "series": v.to_dict("records")})


@app.get("/api/accuracy")
def accuracy(cutoff_hour: int = Query(9, ge=0, le=23)):
    d = _ensure()
    return clean(analysis.accuracy(d["forecasts"], d["actuals"], DAYS, cutoff_hour))


@app.get("/api/data-quality")
def data_quality(cutoff_hour: int = Query(9, ge=0, le=23)):
    d = _ensure()
    a, f = d["actuals"], d["forecasts"]
    lead = (f.startTime - f.publishTime).dt.total_seconds() / 3600
    covered = violations = 0
    for day in DAYS:
        s, cut = analysis.snapshot(f, day, cutoff_hour)
        covered += int(len(s) > 0)
        violations += int(len(s) > 0 and s.publishTime.max() > cut)
    late = int((lead < 0).sum())
    return clean({"actual_rows": len(a), "expected_actual_rows": 32 * 48,
                  "actual_from": a.startTime.min(), "actual_to": a.startTime.max(),
                  "actual_missing": int(a.actual.isna().sum()), "actual_mean": a.actual.mean(),
                  "actual_min": a.actual.min(), "actual_max": a.actual.max(),
                  "forecast_rows": len(f), "forecast_publishes": int(f.publishTime.nunique()),
                  "publish_from": f.publishTime.min(), "publish_to": f.publishTime.max(),
                  "forecast_mean": f.forecast.mean(), "lead_min": lead.min(),
                  "lead_median": lead.median(), "lead_max": lead.max(),
                  "late_rows": late, "late_pct": late / len(f) * 100,
                  "days_covered": covered, "total_days": len(DAYS), "cutoff_violations": violations})


@app.get("/api/forecast.csv")
def forecast_csv(date: dt.date, cutoff_hour: int = 9, percentile: float = 0.95):
    d = _ensure()
    v, _ = analysis.forecast_view(d["forecasts"], d["actuals"], date, cutoff_hour, DAYS, percentile)
    return Response(v.to_csv(index=False), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=forecast_{date}.csv"})


@app.get("/api/accuracy.csv")
def accuracy_csv(cutoff_hour: int = 9):
    d = _ensure()
    daily = analysis.accuracy(d["forecasts"], d["actuals"], DAYS, cutoff_hour)["daily"]
    return Response(pd.DataFrame(daily).to_csv(index=False), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=accuracy_daily.csv"})


STATIC = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(STATIC):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        root = os.path.realpath(STATIC)
        cand = os.path.realpath(os.path.join(root, path))
        if path and cand.startswith(root + os.sep) and os.path.isfile(cand):
            return FileResponse(cand)  # e.g. favicon.svg
        return FileResponse(os.path.join(STATIC, "index.html"))
