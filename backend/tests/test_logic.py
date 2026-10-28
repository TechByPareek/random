import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from app import main  # noqa: E402


def test_horizon_mode_never_uses_late_forecasts():
    for h in (0, 12, 24, 48):
        chosen = main.latest_forecast_by_horizon(h)
        assert (chosen["horizon_h"] >= h).all()


def test_decision_mode_uses_only_forecasts_published_before_decision():
    chosen = main.latest_forecast_by_decision(9)
    decision_time = (
        chosen["startTime"].dt.normalize()
        - pd.Timedelta(days=1)
        + pd.Timedelta(hours=9)
    )
    assert (chosen["publishTime"] <= decision_time).all()


def test_one_forecast_per_target_time():
    chosen = main.latest_forecast_by_decision(9)
    assert chosen["startTime"].is_unique


def test_metrics_simple_case():
    df = pd.DataFrame({"actual": [10, 20, 30], "forecast": [12, 18, 35]})
    df["error"] = df["forecast"] - df["actual"]
    df["abs_error"] = df["error"].abs()
    m = main.compute_metrics(df)
    assert m["n"] == 3
    assert abs(m["mae"] - 3.0) < 1e-9
    assert abs(m["bias"] - 5 / 3) < 1e-9