"""Layer1_Collection public API.

Expose the canonical observation types plus lightweight sensor adapters so
callers do not need to know the internal module layout.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from Config.config import DATA_DIR
from engine.Layer1_Collection.observation import (
    ActionType,
    ObservationDeduplicator,
    ObservationRecord,
    SourceType,
)
from engine.Layer1_Collection.sensors.gdelt_sensor import (
    GDELTSensorAdapter as GDELTSensor,
    sense_gdelt,
)
from engine.Layer3_StateModel.providers.comtrade_provider import ComtradeProvider
from engine.Layer3_StateModel.providers.worldbank_provider import WorldBankProvider


class WorldBankSensor:
    """Compatibility adapter over the World Bank provider."""

    def __init__(self, data_dir: str | None = None):
        self.provider = WorldBankProvider(data_dir or DATA_DIR)

    def get_state(self, country_code: str, years_back: int = 5) -> Dict[str, Any]:
        signal = self.provider.get_signal(country_code, f"{datetime.now(timezone.utc).year}-12-31") or {}
        if not signal:
            return {"status": "no_data", "economic_pressure": 0.0, "vulnerability_score": 0.0, "indicators": {}}

        inflation = float(signal.get("inflation") or 0.0)
        debt = float(signal.get("debt_to_gdp") or 0.0)
        pressure = max(0.0, min(1.0, max(abs(inflation) / 20.0, debt / 150.0)))
        vulnerability = max(0.0, min(1.0, ((abs(inflation) / 20.0) + (debt / 150.0)) / 2.0))
        indicators = {
            "gdp": {"value": float(signal.get("gdp") or 0.0), "year": signal.get("gdp_year")},
            "inflation": {"value": inflation, "year": signal.get("inflation_year")},
            "debt_to_gdp": {"value": debt, "year": signal.get("debt_year")},
            "gdp_growth": {"value": signal.get("gdp_growth"), "year": signal.get("gdp_year")},
        }
        return {
            "status": "ok",
            "economic_pressure": round(pressure, 4),
            "vulnerability_score": round(vulnerability, 4),
            "indicators": indicators,
        }


class ComtradeSensor:
    """Compatibility adapter over the UN Comtrade provider."""

    def __init__(self, data_dir: str | None = None):
        self.provider = ComtradeProvider(data_dir or DATA_DIR)

    def get_state(self, reporter: str, partner: str = "") -> Dict[str, Any]:
        signal = self.provider.get_signal(reporter, f"{datetime.now(timezone.utc).year}-12-31") or {}
        if not signal:
            return {"status": "no_data", "partner": partner or "", "leverage_index": 0.0}
        return {
            "status": "ok",
            "partner": partner or str(signal.get("partner", "") or ""),
            **signal,
        }


def collect_all(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Small compatibility helper for legacy callers."""
    return {
        "gdelt": sense_gdelt(*args, **kwargs),
    }


__all__ = [
    "ObservationRecord",
    "ActionType",
    "SourceType",
    "ObservationDeduplicator",
    "GDELTSensor",
    "WorldBankSensor",
    "ComtradeSensor",
    "sense_gdelt",
    "collect_all",
]
