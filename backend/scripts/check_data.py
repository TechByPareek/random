import pandas as pd
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

a = pd.read_csv(DATA / "actuals.csv")
f = pd.read_csv(DATA / "forecasts.csv")
a["startTime"] = pd.to_datetime(a["startTime"], utc=True)
f["startTime"] = pd.to_datetime(f["startTime"], utc=True)
f["publishTime"] = pd.to_datetime(f["publishTime"], utc=True)
f["horizon_h"] = (f["startTime"] - f["publishTime"]).dt.total_seconds() / 3600

print("===== ACTUALS =====")
print("rows:", len(a), "(expected about 1488)")
print("first time:", a["startTime"].min())
print("last time: ", a["startTime"].max())
print("missing values:", int(a["generation"].isna().sum()))
print("min / max MW:", a["generation"].min(), "/", a["generation"].max())

print()
print("===== FORECASTS =====")
print("rows:", len(f))
print("different target times:", f["startTime"].nunique())
print("forecasts per target time (average):", round(len(f) / f["startTime"].nunique(), 1))
print("first publishTime:", f["publishTime"].min())
print("last publishTime: ", f["publishTime"].max())
print("horizon in hours (min / median / max):",
      round(f["horizon_h"].min(), 1), "/",
      round(f["horizon_h"].median(), 1), "/",
      round(f["horizon_h"].max(), 1))
print("forecasts published AFTER their target time:", int((f["horizon_h"] < 0).sum()))
print("missing values:", int(f["generation"].isna().sum()))

print()
print("===== SAMPLE: all forecasts for one target time =====")
t = pd.Timestamp("2026-01-15 12:00:00", tz="UTC")
print(f[f["startTime"] == t].sort_values("publishTime")[["publishTime", "generation", "horizon_h"]].to_string(index=False))