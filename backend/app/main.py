from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DATA = Path(__file__).resolve().parents[1] / "data"

# ---------- Load data once when the server starts ----------
actuals = pd.read_csv(DATA / "actuals.csv")
forecasts = pd.read_csv(DATA / "forecasts.csv")

actuals["startTime"] = pd.to_datetime(actuals["startTime"], utc=True)
forecasts["startTime"] = pd.to_datetime(forecasts["startTime"], utc=True)
forecasts["publishTime"] = pd.to_datetime(forecasts["publishTime"], utc=True)

actuals = actuals.rename(columns={"generation": "actual"})

# Scope: decisions made in January 2026 (day D-1) -> delivery days 2 Jan to 1 Feb 2026
SCOPE_START = pd.Timestamp("2026-01-02", tz="UTC")
SCOPE_END = pd.Timestamp("2026-02-02", tz="UTC")  # exclusive
actuals = actuals[(actuals["startTime"] >= SCOPE_START) & (actuals["startTime"] < SCOPE_END)]
forecasts = forecasts[(forecasts["startTime"] >= SCOPE_START) & (forecasts["startTime"] < SCOPE_END)]

# horizon = how many hours BEFORE the target time the forecast was published
forecasts["horizon_h"] = (
    forecasts["startTime"] - forecasts["publishTime"]
).dt.total_seconds() / 3600

app = FastAPI(title="Wind Forecast Monitor")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ---------- Core logic ----------
def latest_forecast_by_horizon(min_horizon_h: float) -> pd.DataFrame:
    """For each target time, take the latest forecast published at least
    `min_horizon_h` hours before it. Forecasts made later are never used."""
    f = forecasts[forecasts["horizon_h"] >= min_horizon_h]
    idx = f.groupby("startTime")["publishTime"].idxmax()
    return f.loc[idx]


def latest_forecast_by_decision(decision_hour_utc: int) -> pd.DataFrame:
    """For each target time on day D, take the latest forecast published
    at or before `decision_hour_utc` o'clock on day D-1."""
    f = forecasts.copy()
    f["decision_time"] = (
        f["startTime"].dt.normalize()
        - pd.Timedelta(days=1)
        + pd.Timedelta(hours=decision_hour_utc)
    )
    f = f[f["publishTime"] <= f["decision_time"]]
    idx = f.groupby("startTime")["publishTime"].idxmax()
    return f.loc[idx]


def compare_with_actuals(chosen: pd.DataFrame) -> pd.DataFrame:
    df = chosen[["startTime", "publishTime", "generation", "horizon_h"]].rename(
        columns={"generation": "forecast"}
    )
    df = df.merge(actuals, on="startTime", how="inner")
    df["error"] = df["forecast"] - df["actual"]  # positive = forecast too high
    df["abs_error"] = df["error"].abs()
    return df.sort_values("startTime")


def get_matched(mode: str, horizon: float, decision_hour: int) -> pd.DataFrame:
    if mode == "decision":
        return compare_with_actuals(latest_forecast_by_decision(decision_hour))
    return compare_with_actuals(latest_forecast_by_horizon(horizon))


def compute_metrics(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    return {
        "n": int(len(df)),
        "mae": float(df["abs_error"].mean()),
        "rmse": float(np.sqrt((df["error"] ** 2).mean())),
        "bias": float(df["error"].mean()),
        "p50_abs_error": float(df["abs_error"].quantile(0.5)),
        "p90_abs_error": float(df["abs_error"].quantile(0.9)),
        "p99_abs_error": float(df["abs_error"].quantile(0.99)),
        "mean_actual": float(df["actual"].mean()),
        "nmae_pct": float(df["abs_error"].mean() / df["actual"].mean() * 100),
    }


def iso(ts) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- API endpoints ----------
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/series")
def series(
    start: str = "2026-01-02T00:00:00Z",
    end: str = "2026-02-01T23:30:00Z",
    mode: str = Query("horizon", pattern="^(horizon|decision)$"),
    horizon: float = Query(24, ge=0, le=66),
    decision_hour: int = Query(9, ge=0, le=23),
):
    """Actual vs forecast over time, plus error numbers for that period."""
    df = get_matched(mode, horizon, decision_hour)
    df = df[
        (df["startTime"] >= pd.Timestamp(start)) & (df["startTime"] <= pd.Timestamp(end))
    ]
    return {
        "mode": mode,
        "horizon_h": horizon,
        "decision_hour_utc": decision_hour,
        "points": [
            {
                "t": iso(r.startTime),
                "actual": float(r.actual),
                "forecast": float(r.forecast),
                "error": float(r.error),
                "published": iso(r.publishTime),
            }
            for r in df.itertuples()
        ],
        "metrics": compute_metrics(df),
    }


@app.get("/api/metrics-by-horizon")
def metrics_by_horizon(step: int = 3, max_h: int = 66):
    """How the error changes as the forecast is made further ahead."""
    out = []
    for h in range(0, max_h + 1, step):
        m = compute_metrics(compare_with_actuals(latest_forecast_by_horizon(h)))
        if m:
            out.append({"horizon_h": h, **m})
    return out


@app.get("/api/error-by-hour")
def error_by_hour(
    mode: str = Query("horizon", pattern="^(horizon|decision)$"),
    horizon: float = Query(24, ge=0, le=66),
    decision_hour: int = Query(9, ge=0, le=23),
):
    """Average error for each hour of the day (UTC)."""
    df = get_matched(mode, horizon, decision_hour)
    df["hour"] = df["startTime"].dt.hour
    g = df.groupby("hour")["abs_error"].mean().reset_index()
    return [{"hour": int(r.hour), "mae": float(r.abs_error)} for r in g.itertuples()]


@app.get("/api/decision")
def decision(decision_time: Optional[str] = None):
    """What the buyer sees at a decision moment: for every hour of the NEXT day,
    the latest forecast published at or before decision_time, plus a likely range."""
    if decision_time is None:
        raise HTTPException(400, "decision_time required, e.g. 2026-01-14T09:00:00Z")
    dt = pd.Timestamp(decision_time)
    if dt.tzinfo is None:
        dt = dt.tz_localize("UTC")
    day = (dt + pd.Timedelta(days=1)).normalize()

    f = forecasts[
        (forecasts["publishTime"] <= dt)
        & (forecasts["startTime"] >= day)
        & (forecasts["startTime"] < day + pd.Timedelta(days=1))
    ]
    if f.empty:
        return {"decision_time": iso(dt), "delivery_day": iso(day), "points": []}

    idx = f.groupby("startTime")["publishTime"].idxmax()
    f = f.loc[idx].sort_values("startTime")

    # typical error of forecasts made at this same time of day
    m = compute_metrics(get_matched("decision", 24, dt.hour))
    band = m.get("p90_abs_error", 0.0)
    return {
        "decision_time": iso(dt),
        "delivery_day": iso(day),
        "p90_abs_error": band,
        "points": [
            {
                "t": iso(r.startTime),
                "forecast": float(r.generation),
                "published": iso(r.publishTime),
                "low": float(max(r.generation - band, 0)),
                "high": float(r.generation + band),
            }
            for r in f.itertuples()
        ],
    }


@app.get("/api/bias-by-forecast-level")
def bias_by_forecast_level(
    mode: str = Query("decision", pattern="^(horizon|decision)$"),
    horizon: float = Query(24, ge=0, le=66),
    decision_hour: int = Query(9, ge=0, le=23),
):
    """Average error grouped by how much wind the forecast predicted.
    The forecast level is known at decision time, so this is usable for planning."""
    df = get_matched(mode, horizon, decision_hour)
    bins = [0, 6000, 9000, 12000, 15000, 30000]
    labels = ["under 6 GW", "6-9 GW", "9-12 GW", "12-15 GW", "over 15 GW"]
    df["level"] = pd.cut(df["forecast"], bins=bins, labels=labels, include_lowest=True)
    g = (
        df.groupby("level", observed=True)
        .agg(bias=("error", "mean"), mae=("abs_error", "mean"), n=("error", "size"))
        .reset_index()
    )
    return [
        {"level": str(r.level), "bias": float(r.bias), "mae": float(r.mae), "n": int(r.n)}
        for r in g.itertuples()
    ]