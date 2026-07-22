"""
Prophet Forecaster — Time-Series Trajectory Prediction
=======================================================

Uses Meta's Prophet for trend, seasonality, and changepoint detection
on historical SRE scores. Falls back gracefully to numpy if Prophet unavailable.

Wire into: unified_pipeline → Layer 5: Trajectory Forecast
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("Layer5_Trajectory.prophet")

try:
    from prophet import Prophet as _Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logger.info("Prophet not installed. Using numpy fallback for forecasting.")


def forecast_trajectory(
    scores: List[Dict[str, Any]],
    horizon_days: int = 30,
) -> Dict[str, Any]:
    """Forecast SRE trajectory using Prophet or numpy fallback.

    Args:
        scores: List of {timestamp, sre_score} dicts, sorted by time
        horizon_days: Days to forecast forward

    Returns:
        {
            "forecast_7d": float,
            "forecast_14d": float,
            "forecast_30d": float,
            "trend": "ESCALATING" | "STABLE" | "DE_ESCALATING",
            "changepoints": list[str],
            "confidence_interval": [lower, upper],
            "method": "prophet" | "numpy_fallback",
            "rmse": float or None,
        }
    """
    if not scores or len(scores) < 2:
        return {
            "forecast_7d": 0.0,
            "forecast_14d": 0.0,
            "forecast_30d": 0.0,
            "trend": "STABLE",
            "changepoints": [],
            "confidence_interval": [0.0, 0.0],
            "method": "insufficient_data",
            "rmse": None,
        }

    if PROPHET_AVAILABLE:
        return _prophet_forecast(scores, horizon_days)
    else:
        return _numpy_forecast(scores, horizon_days)


def _prophet_forecast(
    scores: List[Dict[str, Any]],
    horizon_days: int,
) -> Dict[str, Any]:
    """Prophet-based forecasting with trend + changepoint detection."""
    import pandas as pd

    # Prepare dataframe
    df = pd.DataFrame([
        {"ds": s.get("timestamp", ""), "y": float(s.get("sre_score", 0.0))}
        for s in scores
    ])
    df["ds"] = pd.to_datetime(df["ds"])
    df = df.dropna()

    if len(df) < 3:
        return _numpy_forecast(scores, horizon_days)

    # Fit Prophet
    model = _Prophet(
        changepoint_prior_scale=0.05,
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=False,
    )
    model.fit(df)

    # Forecast
    future = model.make_future_dataframe(periods=horizon_days)
    forecast = model.predict(future)

    # Extract predictions
    now_idx = len(df) - 1
    pred_7d = float(forecast.iloc[min(now_idx + 7, len(forecast) - 1)]["yhat"])
    pred_14d = float(forecast.iloc[min(now_idx + 14, len(forecast) - 1)]["yhat"])
    pred_30d = float(forecast.iloc[-1]["yhat"])

    # Trend direction
    recent = df["y"].values[-5:]
    slope = np.polyfit(range(len(recent)), recent, 1)[0]
    if slope > 0.02:
        trend = "ESCALATING"
    elif slope < -0.02:
        trend = "DE_ESCALATING"
    else:
        trend = "STABLE"

    # Changepoints
    changepoints = [
        str(cp.date()) for cp in model.changepoints
        if cp > df["ds"].iloc[-1] - pd.Timedelta(days=30)
    ]

    # Confidence interval
    last_row = forecast.iloc[-1]
    ci = [float(last_row["yhat_lower"]), float(last_row["yhat_upper"])]

    # RMSE
    y_true = df["y"].values
    y_pred = forecast["yhat"].values[:len(df)]
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

    return {
        "forecast_7d": round(pred_7d, 4),
        "forecast_14d": round(pred_14d, 4),
        "forecast_30d": round(pred_30d, 4),
        "trend": trend,
        "changepoints": changepoints[:5],
        "confidence_interval": [round(ci[0], 4), round(ci[1], 4)],
        "method": "prophet",
        "rmse": round(rmse, 4),
    }


def _numpy_forecast(
    scores: List[Dict[str, Any]],
    horizon_days: int,
) -> Dict[str, Any]:
    """Simple linear regression fallback when Prophet is not available."""
    values = np.array([float(s.get("sre_score", 0.0)) for s in scores])
    x = np.arange(len(values))

    if len(values) >= 3:
        slope, intercept = np.polyfit(x, values, 1)
    else:
        slope = 0.0
        intercept = np.mean(values)

    last_val = values[-1]
    forecast_7d = max(0.0, min(1.0, intercept + slope * (len(values) + 7)))
    forecast_14d = max(0.0, min(1.0, intercept + slope * (len(values) + 14)))
    forecast_30d = max(0.0, min(1.0, intercept + slope * (len(values) + 30)))

    # Trend
    recent = values[-5:] if len(values) >= 5 else values
    recent_slope = np.polyfit(range(len(recent)), recent, 1)[0] if len(recent) >= 2 else 0.0
    if recent_slope > 0.02:
        trend = "ESCALATING"
    elif recent_slope < -0.02:
        trend = "DE_ESCALATING"
    else:
        trend = "STABLE"

    # Simple confidence: ±1 std dev
    std = float(np.std(values)) if len(values) > 1 else 0.05
    ci = [max(0.0, forecast_30d - std), min(1.0, forecast_30d + std)]

    # RMSE
    y_pred = intercept + slope * x
    rmse = float(np.sqrt(np.mean((values - y_pred) ** 2)))

    return {
        "forecast_7d": round(forecast_7d, 4),
        "forecast_14d": round(forecast_14d, 4),
        "forecast_30d": round(forecast_30d, 4),
        "trend": trend,
        "changepoints": [],
        "confidence_interval": [round(ci[0], 4), round(ci[1], 4)],
        "method": "numpy_fallback",
        "rmse": round(rmse, 4),
    }
