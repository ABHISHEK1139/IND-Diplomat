"""
Translate provider payloads into Layer-1 ObservationRecord objects.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from engine.Layer1_Collection.observation import ActionType, ObservationRecord, SourceType


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clip01(value: Any) -> float:
    return max(0.0, min(1.0, _safe_float(value, 0.0)))


def _normalize_country(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalize_date(value: Any, fallback: str) -> str:
    token = str(value or "").strip()
    if not token:
        return fallback
    if token.isdigit() and len(token) == 8:
        return f"{token[0:4]}-{token[4:6]}-{token[6:8]}"
    if len(token) == 10 and token[4] == "-" and token[7] == "-":
        return token
    return fallback


def _short_hash(payload: Any) -> str:
    raw = str(payload or "").encode("utf-8", errors="ignore")
    return hashlib.md5(raw).hexdigest()[:10]


def _gdelt_action(event_code: str, tension: float) -> ActionType:
    code = str(event_code or "").strip()
    if code.startswith(("18", "19", "20")):
        return ActionType.MOBILIZE
    if code.startswith(("17", "13", "14")):
        return ActionType.THREATEN_MILITARY
    if code.startswith(("10", "11", "12")):
        return ActionType.DIPLOMACY
    if tension >= 0.7:
        return ActionType.PRESSURE
    return ActionType.OBSERVATION


def from_gdelt(event: Dict[str, Any], *, country_code: str, fallback_date: str) -> Optional[ObservationRecord]:
    if not isinstance(event, dict):
        return None

    actor = _normalize_country(event.get("Actor1CountryCode") or country_code)
    target = _normalize_country(event.get("Actor2CountryCode"))
    sql_date = _normalize_date(event.get("SQLDATE") or event.get("date"), fallback_date)
    event_code = str(event.get("EventCode") or event.get("event_code") or "").strip()
    tension = _clip01(event.get("tension", abs(_safe_float(event.get("GoldsteinScale"), 0.0)) / 10.0))
    reference = str(event.get("SOURCEURL") or event.get("url") or "https://www.gdeltproject.org/").strip()
    obs_id = f"gdelt_{actor or country_code}_{sql_date}_{_short_hash(event_code + reference)}"

    actors = [token for token in [actor, target] if token]
    direction = f"{actor}->{target}" if actor and target else actor

    return ObservationRecord(
        obs_id=obs_id,
        source="gdelt",
        source_type=SourceType.EVENT_MONITOR,
        event_date=sql_date,
        report_date=sql_date,
        actors=actors,
        action_type=_gdelt_action(event_code, tension),
        intensity=tension,
        direction=direction,
        confidence=_clip01(0.45 + (0.5 * tension)),
        raw_reference=reference,
        raw_data=dict(event),
        metadata={
            "dataset": "GDELT",
            "event_code": event_code,
        },
    )


def _worldbank_intensity(series_code: str, value: float) -> float:
    if series_code == "FP.CPI.TOTL.ZG":
        return _clip01(value / 15.0)
    if series_code == "GC.DOD.TOTL.GD.ZS":
        return _clip01(value / 120.0)
    if series_code == "NY.GDP.MKTP.CD":
        return _clip01(min(abs(value), 2.0e13) / 2.0e13)
    return _clip01(abs(value) / 100.0)


def from_worldbank(
    *,
    country_code: str,
    series_code: str,
    value: float,
    year: int,
    fallback_date: str,
) -> ObservationRecord:
    event_date = _normalize_date(f"{int(year)}-12-31", fallback_date)
    intensity = _worldbank_intensity(series_code, _safe_float(value, 0.0))
    obs_id = f"worldbank_{country_code}_{series_code}_{year}"

    return ObservationRecord(
        obs_id=obs_id,
        source="world_bank",
        source_type=SourceType.STATISTICAL_AGENCY,
        event_date=event_date,
        report_date=event_date,
        actors=[_normalize_country(country_code)],
        action_type=ActionType.ECONOMIC_INDICATOR,
        intensity=intensity,
        confidence=0.85,
        raw_reference="https://data.worldbank.org/",
        raw_data={"series": series_code, "value": value, "year": int(year)},
        metadata={"dataset": "WorldBank"},
    )


def from_comtrade(signal: Dict[str, Any], *, country_code: str, fallback_date: str) -> Optional[ObservationRecord]:
    if not isinstance(signal, dict):
        return None
    if bool(signal.get("proxy", False)):
        return None

    event_date = _normalize_date(signal.get("date"), fallback_date)
    partner = _normalize_country(signal.get("partner"))
    leverage = _clip01(signal.get("leverage_index", 0.0))
    obs_id = f"comtrade_{country_code}_{partner or 'WORLD'}_{event_date}"
    actors = [_normalize_country(country_code)]
    if partner:
        actors.append(partner)

    return ObservationRecord(
        obs_id=obs_id,
        source="comtrade",
        source_type=SourceType.STATISTICAL_AGENCY,
        event_date=event_date,
        report_date=event_date,
        actors=actors,
        action_type=ActionType.TRADE_FLOW,
        intensity=leverage,
        direction=f"{country_code}->{partner}" if partner else country_code,
        confidence=0.90,
        raw_reference="https://comtradeplus.un.org/",
        raw_data=dict(signal),
        metadata={"dataset": "UNComtrade"},
    )


def build_observations_from_provider_signals(
    *,
    country_code: str,
    as_of_date: str,
    signals: Dict[str, Any],
) -> List[ObservationRecord]:
    observations: List[ObservationRecord] = []
    normalized_country = _normalize_country(country_code)

    gdelt = signals.get("gdelt")
    if isinstance(gdelt, dict):
        evidence_rows = list(gdelt.get("evidence", []) or [])
        if evidence_rows:
            for row in evidence_rows:
                if not isinstance(row, dict):
                    continue
                event = {
                    "Actor1CountryCode": normalized_country,
                    "Actor2CountryCode": "",
                    "EventCode": "190",
                    "SQLDATE": row.get("date"),
                    "GoldsteinScale": _safe_float(gdelt.get("tension", 0.0), 0.0) * 10.0,
                    "SOURCEURL": row.get("url"),
                    "tension": gdelt.get("tension", 0.0),
                }
                obs = from_gdelt(event, country_code=normalized_country, fallback_date=as_of_date)
                if obs is not None:
                    observations.append(obs)
        else:
            summary_event = {
                "Actor1CountryCode": normalized_country,
                "Actor2CountryCode": "",
                "EventCode": "190",
                "SQLDATE": gdelt.get("date"),
                "GoldsteinScale": _safe_float(gdelt.get("tension", 0.0), 0.0) * 10.0,
                "SOURCEURL": "https://www.gdeltproject.org/",
                "tension": gdelt.get("tension", 0.0),
            }
            obs = from_gdelt(summary_event, country_code=normalized_country, fallback_date=as_of_date)
            if obs is not None:
                observations.append(obs)

    world_bank = signals.get("world_bank")
    if isinstance(world_bank, dict):
        wb_mappings = [
            ("NY.GDP.MKTP.CD", "gdp", "gdp_year"),
            ("FP.CPI.TOTL.ZG", "inflation", "inflation_year"),
            ("GC.DOD.TOTL.GD.ZS", "debt_to_gdp", "debt_year"),
        ]
        for series_code, value_key, year_key in wb_mappings:
            value = world_bank.get(value_key)
            year = world_bank.get(year_key)
            if value is None or year is None:
                continue
            observations.append(
                from_worldbank(
                    country_code=normalized_country,
                    series_code=series_code,
                    value=_safe_float(value, 0.0),
                    year=int(float(year)),
                    fallback_date=as_of_date,
                )
            )

    comtrade = signals.get("un_comtrade")
    obs = from_comtrade(comtrade, country_code=normalized_country, fallback_date=as_of_date)
    if obs is not None:
        observations.append(obs)

    return observations


__all__ = [
    "from_gdelt",
    "from_worldbank",
    "from_comtrade",
    "build_observations_from_provider_signals",
]
