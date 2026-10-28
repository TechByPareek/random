import numpy as np
import pandas as pd
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

a = pd.read_csv(DATA / "actuals.csv")
f = pd.read_csv(DATA / "forecasts.csv")
a["startTime"] = pd.to_datetime(a["startTime"], utc=True)
f["startTime"] = pd.to_datetime(f["startTime"], utc=True)
f["publishTime"] = pd.to_datetime(f["publishTime"], utc=True)
f["horizon_h"] = (f["startTime"] - f["publishTime"]).dt.total_seconds() / 3600
a = a.rename(columns={"generation": "actual"})

# newest forecast published at or before each target time
g = f[f["horizon_h"] >= 0]
best = g.loc[g.groupby("startTime")["publishTime"].idxmax()][["startTime", "generation"]]
best = best.rename(columns={"generation": "forecast"})

print("===== 1. TIME SHIFT TEST (forecast target time moved by N minutes) =====")
print("shift_min   n    MAE    bias   correlation")
for shift in range(-180, 181, 30):
    b = best.copy()
    b["startTime"] = b["startTime"] + pd.Timedelta(minutes=shift)
    m = b.merge(a, on="startTime")
    err = m["forecast"] - m["actual"]
    print(f"{shift:6d}   {len(m):4d}  {err.abs().mean():6.0f}  {err.mean():6.0f}   {m['forecast'].corr(m['actual']):.4f}")

print()
print("===== 2. AVERAGE MW =====")
m = best.merge(a, on="startTime")
print("average forecast:", round(m["forecast"].mean()))
print("average actual:  ", round(m["actual"].mean()))
print("ratio forecast / actual:", round(m["forecast"].mean() / m["actual"].mean(), 3))

print()
print("===== 3. BIAS BY WEEK OF JANUARY =====")
m["week"] = m["startTime"].dt.isocalendar().week
m["error"] = m["forecast"] - m["actual"]
print(m.groupby("week")["error"].agg(["mean", "count"]).round(0).to_string())

print()
print("===== 4. SHARE OF HOURS WHERE FORECAST > ACTUAL =====")
print(round((m["error"] > 0).mean() * 100, 1), "%")