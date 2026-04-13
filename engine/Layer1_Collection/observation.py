"""
Layer1_Collection.observation — Canonical observation model
============================================================

Provides the cross-layer observation record, action/source enums,
deduplication, and convenience converters for GDELT, World Bank,
and UN-Comtrade provider data.

Every Layer-3/Layer-4 module that touches raw observations should
import from this module (or from ``contracts.observation`` which
re-exports everything here).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Enums ──────────────────────────────────────────────────────


class ActionType(Enum):
    """Taxonomy of geopolitical action types (CAMEO-inspired, 25+ members)."""

    # Diplomacy / Cooperative
    STATEMENT = "statement"
    APPEAL = "appeal"
    CONSULTATION = "consultation"
    DIPLOMACY = "diplomacy"
    COOPERATION = "cooperation"
    TRADE_AGREEMENT = "trade_agreement"
    AID = "aid"
    YIELD = "yield"

    # Economic
    SANCTION = "sanction"
    TRADE_RESTRICTION = "trade_restriction"
    TRADE_FLOW = "trade_flow"
    ECONOMIC_INDICATOR = "economic_indicator"
    ARMS_DEAL = "arms_deal"

    # Pressure / Conflict
    PRESSURE = "pressure"
    THREATEN_MILITARY = "threaten_military"
    PROTEST = "protest"
    FORCE_POSTURE = "force_posture"
    MOBILIZE = "mobilize"
    WAR = "war"
    MASS_VIOLENCE = "mass_violence"
    CYBER_ATTACK = "cyber_attack"

    # Internal / Governance
    ELECTION = "election"
    COUP_ATTEMPT = "coup_attempt"
    POLICY_CHANGE = "policy_change"
    EXPULSION = "expulsion"
    BLOCKADE = "blockade"
    VIOLENCE = "violence"
    ARMS_TRANSFER = "arms_transfer"

    # Neutral / Other
    OBSERVATION = "observation"
    INTELLIGENCE = "intelligence"
    ESPIONAGE = "espionage"
    HUMANITARIAN = "humanitarian"
    INVESTIGATION = "investigation"


class SourceType(Enum):
    """Taxonomy of observation source types."""

    EVENT_MONITOR = "event_monitor"
    STATISTICAL_AGENCY = "statistical_agency"
    GOVERNMENT_RELEASE = "government_release"
    INTELLIGENCE_REPORT = "intelligence_report"
    MEDIA_OUTLET = "media_outlet"
    ACADEMIC = "academic"
    SOCIAL_MEDIA = "social_media"


# ── Observation Record ─────────────────────────────────────────


@dataclass
class ObservationRecord:
    """
    Canonical Layer-1 observation.

    Every sensor / provider output is normalised into this shape before
    Layer-2 storage or Layer-3 reasoning sees it.
    """

    obs_id: str
    source: str
    source_type: SourceType
    event_date: str
    report_date: str
    actors: List[str] = field(default_factory=list)
    action_type: ActionType = ActionType.OBSERVATION
    intensity: float = 0.0
    direction: str = ""
    confidence: float = 0.5
    confidence_source: float = 0.0
    raw_reference: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    mention_count: int = 1
    ingest_date: str = ""
    dedup_key: str = ""

    def __post_init__(self) -> None:
        if not self.ingest_date:
            self.ingest_date = datetime.now().strftime("%Y-%m-%d")
        if self.confidence_source <= 0.0 and self.confidence > 0.0:
            self.confidence_source = self.confidence
        if not self.dedup_key:
            self.dedup_key = self._compute_dedup_key()

    # ── helpers ────────────────────────────────────────────────

    def _compute_dedup_key(self) -> str:
        parts = [
            "|".join(sorted(self.actors)),
            self.action_type.value if isinstance(self.action_type, ActionType) else str(self.action_type),
            self.event_date,
        ]
        raw = ":".join(parts).encode("utf-8")
        return hashlib.md5(raw).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Enum):
                d[k] = v.value
            else:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObservationRecord":
        data = dict(data)
        if "action_type" in data and isinstance(data["action_type"], str):
            try:
                data["action_type"] = ActionType(data["action_type"])
            except ValueError:
                data["action_type"] = ActionType.OBSERVATION
        if "source_type" in data and isinstance(data["source_type"], str):
            try:
                data["source_type"] = SourceType(data["source_type"])
            except ValueError:
                data["source_type"] = SourceType.EVENT_MONITOR
        valid = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in valid})


# ── Deduplicator ───────────────────────────────────────────────


class ObservationDeduplicator:
    """Merge duplicate observations by dedup_key."""

    def __init__(self) -> None:
        self._seen: Dict[str, ObservationRecord] = {}

    def process_batch(self, observations: List[ObservationRecord]) -> List[ObservationRecord]:
        groups: Dict[str, List[ObservationRecord]] = {}
        for obs in observations:
            groups.setdefault(obs.dedup_key, []).append(obs)

        merged: List[ObservationRecord] = []
        for _key, group in groups.items():
            if len(group) == 1:
                merged.append(group[0])
                continue
            best = max(group, key=lambda o: o.confidence)
            total_mentions = sum(o.mention_count for o in group)
            max_intensity = max(o.intensity for o in group)
            merged_obs = ObservationRecord(
                obs_id=best.obs_id,
                source=best.source,
                source_type=best.source_type,
                event_date=best.event_date,
                report_date=best.report_date,
                actors=best.actors,
                action_type=best.action_type,
                intensity=max_intensity,
                direction=best.direction,
                confidence=best.confidence,
                confidence_source=best.confidence_source,
                raw_reference=best.raw_reference,
                raw_data=best.raw_data,
                metadata={**best.metadata, "merged_count": len(group)},
                mention_count=total_mentions,
                dedup_key=_key,
            )
            merged.append(merged_obs)
        return merged

    def reset(self) -> None:
        self._seen.clear()


# Singleton
deduplicator = ObservationDeduplicator()


# ── CAMEO event-root → ActionType mapping ──────────────────────

_EVENT_ROOT_TO_ACTION: Dict[str, ActionType] = {
    "01": ActionType.STATEMENT,
    "02": ActionType.APPEAL,
    "03": ActionType.COOPERATION,
    "04": ActionType.CONSULTATION,
    "05": ActionType.DIPLOMACY,
    "06": ActionType.COOPERATION,
    "07": ActionType.AID,
    "08": ActionType.YIELD,
    "09": ActionType.OBSERVATION,
    "10": ActionType.PRESSURE,
    "11": ActionType.STATEMENT,
    "12": ActionType.PRESSURE,
    "13": ActionType.THREATEN_MILITARY,
    "14": ActionType.PROTEST,
    "15": ActionType.FORCE_POSTURE,
    "16": ActionType.TRADE_RESTRICTION,
    "17": ActionType.PRESSURE,
    "18": ActionType.WAR,
    "19": ActionType.MOBILIZE,
    "20": ActionType.MASS_VIOLENCE,
}

# ── Sub-code overrides ─────────────────────────────────────────
_EVENT_CODE_OVERRIDES: Dict[str, ActionType] = {
    "057": ActionType.TRADE_AGREEMENT,
    "163": ActionType.SANCTION,
    "173": ActionType.PRESSURE,
}


def _goldstein_to_action(goldstein: float) -> ActionType:
    if goldstein <= -8.0:
        return ActionType.WAR
    if goldstein <= -5.0:
        return ActionType.THREATEN_MILITARY
    if goldstein <= -2.0:
        return ActionType.PRESSURE
    if goldstein >= 5.0:
        return ActionType.COOPERATION
    return ActionType.OBSERVATION


def _goldstein_to_intensity(goldstein: float) -> float:
    return min(1.0, max(0.0, abs(goldstein) / 10.0))


# ── Date helpers ───────────────────────────────────────────────

def _parse_sql_date(raw: Any) -> str:
    s = str(raw or "").strip()
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _parse_date_added(raw: Any) -> str:
    s = str(raw or "").strip()
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


# ── GDELT converter ───────────────────────────────────────────

def gdelt_events_to_observations(
    events: List[Dict[str, Any]],
    source_confidence: float = 0.65,
) -> List[ObservationRecord]:
    """Convert raw GDELT event dicts into ObservationRecord list."""
    observations: List[ObservationRecord] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("GLOBALEVENTID") or event.get("GlobalEventID") or "")
        actor1 = str(event.get("Actor1CountryCode") or "").strip().upper()
        actor2 = str(event.get("Actor2CountryCode") or "").strip().upper()
        event_code = str(event.get("EventCode") or "").strip()
        event_root = str(event.get("EventRootCode") or "").strip()
        if not event_root and len(event_code) >= 2:
            event_root = event_code[:2]
        goldstein = float(event.get("GoldsteinScale") or 0.0)
        num_mentions = int(event.get("NumMentions") or 1)
        source_url = str(event.get("SOURCEURL") or "").strip()
        sql_date = _parse_sql_date(event.get("SQLDATE") or event.get("Day") or "")
        date_added = _parse_date_added(event.get("DATEADDED") or "")
        report_date = date_added if date_added else sql_date

        # Resolve action type: sub-code → root → goldstein fallback
        action: Optional[ActionType] = _EVENT_CODE_OVERRIDES.get(event_code)
        if action is None:
            action = _EVENT_ROOT_TO_ACTION.get(event_root)
        if action is None:
            action = _goldstein_to_action(goldstein)

        actors = [a for a in [actor1, actor2] if a]
        direction_str = f"{actor1} -> {actor2}" if actor1 and actor2 else actor1

        obs = ObservationRecord(
            obs_id=f"gdelt_{event_id}",
            source="gdelt",
            source_type=SourceType.EVENT_MONITOR,
            event_date=sql_date,
            report_date=report_date,
            actors=actors,
            action_type=action,
            intensity=_goldstein_to_intensity(goldstein),
            direction=direction_str,
            confidence=source_confidence,
            confidence_source=source_confidence,
            raw_reference=source_url,
            raw_data=dict(event),
            metadata={
                "dataset": "GDELT",
                "event_code": event_code,
                "goldstein": goldstein,
            },
            mention_count=num_mentions,
        )
        observations.append(obs)
    return observations


# ── World Bank converter ───────────────────────────────────────

def _wb_intensity(indicator_code: str, value: float) -> float:
    if indicator_code == "FP.CPI.TOTL.ZG":
        return min(1.0, max(0.0, abs(value) / 15.0))
    if indicator_code == "GC.DOD.TOTL.GD.ZS":
        return min(1.0, max(0.0, abs(value) / 120.0))
    if indicator_code == "NY.GDP.MKTP.CD":
        return min(1.0, max(0.0, abs(value) / 2.0e13))
    return min(1.0, max(0.0, abs(value) / 100.0))


def worldbank_state_to_observations(
    state: Dict[str, Any],
) -> List[ObservationRecord]:
    """Convert a World Bank state dict into ObservationRecords."""
    observations: List[ObservationRecord] = []
    country_code = str(state.get("country_code") or "").strip().upper()
    timestamp = str(state.get("timestamp") or "")
    report_date = timestamp[:10] if len(timestamp) >= 10 else datetime.now().strftime("%Y-%m-%d")
    indicators = state.get("indicators") or {}

    for indicator_code, details in indicators.items():
        if not isinstance(details, dict):
            continue
        value = details.get("latest_value", 0.0)
        year = details.get("latest_year", 0)
        event_date = f"{int(year)}-12-31" if year else report_date
        intensity = _wb_intensity(indicator_code, float(value or 0.0))

        obs = ObservationRecord(
            obs_id=f"worldbank_{country_code}_{indicator_code}_{year}",
            source="world_bank",
            source_type=SourceType.STATISTICAL_AGENCY,
            event_date=event_date,
            report_date=report_date,
            actors=[country_code],
            action_type=ActionType.ECONOMIC_INDICATOR,
            intensity=intensity,
            direction=country_code,
            confidence=0.90,
            confidence_source=0.90,
            raw_reference="https://data.worldbank.org/",
            raw_data={"indicator": indicator_code, "value": value, "year": year},
            metadata={"dataset": "WorldBank", "indicator_code": indicator_code},
        )
        observations.append(obs)
    return observations


# ── Comtrade converter ─────────────────────────────────────────

def comtrade_state_to_observations(
    state: Dict[str, Any],
) -> List[ObservationRecord]:
    """Convert a UN-Comtrade state dict into ObservationRecords."""
    observations: List[ObservationRecord] = []
    reporter = str(state.get("reporter") or "").strip().upper()
    partner = str(state.get("partner") or "").strip().upper()
    year = state.get("year", 0)
    timestamp = str(state.get("timestamp") or "")
    report_date = timestamp[:10] if len(timestamp) >= 10 else datetime.now().strftime("%Y-%m-%d")
    event_date = f"{int(year)}-12-31" if year else report_date
    leverage = float(state.get("leverage_score") or 0.0)
    total_imports = float(state.get("total_imports") or 0.0)
    total_exports = float(state.get("total_exports") or 0.0)

    actors = [a for a in [reporter, partner] if a]
    direction_str = f"{reporter} -> {partner}" if reporter and partner else reporter

    obs = ObservationRecord(
        obs_id=f"comtrade_{reporter}_{partner}_{year}",
        source="comtrade",
        source_type=SourceType.STATISTICAL_AGENCY,
        event_date=event_date,
        report_date=report_date,
        actors=actors,
        action_type=ActionType.TRADE_FLOW,
        intensity=min(1.0, max(0.0, leverage)),
        direction=direction_str,
        confidence=0.85,
        confidence_source=0.85,
        raw_reference="https://comtradeplus.un.org/",
        raw_data={
            "reporter": reporter,
            "partner": partner,
            "year": year,
            "total_imports": total_imports,
            "total_exports": total_exports,
            "leverage_score": leverage,
        },
        metadata={"dataset": "UNComtrade"},
    )
    observations.append(obs)
    return observations


# ── Public API ─────────────────────────────────────────────────

__all__ = [
    "ActionType",
    "SourceType",
    "ObservationRecord",
    "ObservationDeduplicator",
    "deduplicator",
    "gdelt_events_to_observations",
    "worldbank_state_to_observations",
    "comtrade_state_to_observations",
]
