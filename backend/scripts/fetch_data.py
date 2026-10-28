import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)

CHUNK_DAYS = 5  # download 5 days at a time; make smaller if you get errors

# Decisions are made in January 2026 (day D-1) for delivery on the next day,
# so delivery days run from 2 Jan 2026 to 1 Feb 2026 (inclusive).
# We also keep 1 Jan so the first decision day has context.
DELIVERY_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
DELIVERY_END = datetime(2026, 2, 2, tzinfo=timezone.utc)  # exclusive


def daterange(start, end, step_days):
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=step_days), end)
        yield cur, nxt
        cur = nxt


def fetch_actuals():
    rows = []
    for a, b in daterange(DELIVERY_START, DELIVERY_END, CHUNK_DAYS):
        params = {
            "settlementDateFrom": a.strftime("%Y-%m-%d"),
            "settlementDateTo": (b - timedelta(days=1)).strftime("%Y-%m-%d"),
            "fuelType": "WIND",
            "format": "json",
        }
        r = requests.get(f"{BASE}/FUELHH/stream", params=params, timeout=60)
        r.raise_for_status()
        rows += r.json()
        print("actuals chunk done:", a.date())
    df = pd.DataFrame(rows)
    df = df[df["fuelType"] == "WIND"][["startTime", "generation"]]
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df = df.drop_duplicates("startTime").sort_values("startTime")
    df.to_csv(OUT / "actuals.csv", index=False)
    print("actuals rows saved:", len(df))


def fetch_forecasts():
    rows = []
    # forecasts for early-January targets were published in late December
    start = datetime(2025, 12, 28, tzinfo=timezone.utc)
    for a, b in daterange(start, DELIVERY_END, CHUNK_DAYS):
        params = {
            "publishDateTimeFrom": a.strftime("%Y-%m-%dT%H:%MZ"),
            "publishDateTimeTo": b.strftime("%Y-%m-%dT%H:%MZ"),
            "format": "json",
        }
        r = requests.get(f"{BASE}/WINDFOR/stream", params=params, timeout=60)
        r.raise_for_status()
        rows += r.json()
        print("forecast chunk done:", a.date())
    df = pd.DataFrame(rows)[["publishTime", "startTime", "generation"]]
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df = df.drop_duplicates(["publishTime", "startTime"])
    df = df[(df["startTime"] >= DELIVERY_START) & (df["startTime"] < DELIVERY_END)]
    df.to_csv(OUT / "forecasts.csv", index=False)
    print("forecast rows saved:", len(df))


if __name__ == "__main__":
    fetch_actuals()
    fetch_forecasts()