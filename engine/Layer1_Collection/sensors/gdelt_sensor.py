"""
GDELT Sensor Adapter — Live Event Perception
==============================================

Mental model:
    MoltBot  = journalist   (sparse, delayed, random)
    GDELT    = radar         (structured, continuous, every 15 min)

This adapter converts GDELT event records into **observation dicts**
that the BeliefAccumulator can consume.  It runs once per analysis
cycle, injecting structured event intelligence alongside MoltBot's
text-based observations.

Pipeline:
    1. Live fetch: Download latest GDELT 15-min CSV → parse events → CAMEO→SIG
    2. Fallback:   Read data/tension_history.json  → derive observations
    3. Empty:      If both fail, return [] (MoltBot-only perception).

No NLP.  No LLM.  Pure structured intelligence.

Each GDELT event carries a CAMEO event code.
We map CAMEO root codes → canonical SIG_* tokens.
Then we format observations with Goldstein-scaled evidence_strength.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer1.sensors.gdelt")

# ── CAMEO reference tables (peer module) ──────────────────────────────
try:
    from engine.Layer1_Collection.sensors.cameo_config import (
        CAMEO_EVENT_CODES as _CAMEO_SUBCODES,
        CAMEO_EVENT_ROOT_CODES as _CAMEO_ROOT_LABELS,
        CAMEO_GOLDSTEIN as _CAMEO_GOLDSTEIN,
        MILITARY_ACTOR_TYPES as _MIL_TYPES,
        ARMED_NONSTATE_TYPES as _ARMED_TYPES,
        GOVERNMENT_ACTOR_TYPES as _GOV_TYPES,
        INTERNATIONAL_ACTOR_TYPES as _INTL_TYPES,
    )
except (ImportError, ModuleNotFoundError):
    _CAMEO_SUBCODES: dict = {}
    _CAMEO_ROOT_LABELS: dict = {}
    _CAMEO_GOLDSTEIN: dict = {}
    _MIL_TYPES: set = set()
    _ARMED_TYPES: set = set()
    _GOV_TYPES: set = set()
    _INTL_TYPES: set = set()

# =====================================================================
# CAMEO Root Code → Canonical Signal Mapping
# =====================================================================

CAMEO_TO_SIGNAL: Dict[str, str] = {
    # ── Conflict / Escalation ─────────────────────────────────────
    "18": "SIG_MIL_ESCALATION",         # ASSAULT
    "19": "SIG_MIL_ESCALATION",         # FIGHT
    "20": "SIG_MIL_ESCALATION",         # USE UNCONVENTIONAL MASS VIOLENCE
    "15": "SIG_FORCE_POSTURE",          # EXHIBIT FORCE POSTURE
    "17": "SIG_COERCIVE_PRESSURE",      # COERCE
    "14": "SIG_INTERNAL_INSTABILITY",   # PROTEST
    "13": "SIG_DIP_HOSTILITY",          # THREATEN
    "11": "SIG_DIP_HOSTILITY",          # DISAPPROVE
    "16": "SIG_NEGOTIATION_BREAKDOWN",  # REDUCE RELATIONS
    "12": "SIG_NEGOTIATION_BREAKDOWN",  # REJECT
    "10": "SIG_COERCIVE_BARGAINING",    # DEMAND
    # ── Cooperative / De-escalation ───────────────────────────────
    "04": "SIG_DIPLOMACY_ACTIVE",       # CONSULT
    "05": "SIG_DIPLOMACY_ACTIVE",       # ENGAGE IN DIPLOMATIC COOPERATION
    "06": "SIG_DIPLOMACY_ACTIVE",       # ENGAGE IN MATERIAL COOPERATION
}

# CAMEO_ROOT_LABELS — alias for _CAMEO_ROOT_LABELS (imported from cameo_config).
# Kept as a public name so existing callers (tests, drill) don't break.
CAMEO_ROOT_LABELS: Dict[str, str] = _CAMEO_ROOT_LABELS

DE_ESCALATION_SIGNALS = {"SIG_DIPLOMACY_ACTIVE"}

# =====================================================================
# Sub-code Signal Overrides
# =====================================================================
# When a sub-code's operational nature differs from its root code,
# override the signal.  E.g. 1383 "Threaten unconventional violence"
# is MIL_ESCALATION, not just DIP_HOSTILITY from root 13.

CAMEO_SUBCODE_TO_SIGNAL: Dict[str, str] = {
    # ── Military threats (root 13 = DIP_HOSTILITY → upgrade) ─────
    "138":  "SIG_MIL_ESCALATION",         # Threaten military force
    "1381": "SIG_MIL_ESCALATION",         # Threaten blockade
    "1382": "SIG_MIL_ESCALATION",         # Threaten occupation
    "1383": "SIG_MIL_ESCALATION",         # Threaten unconventional violence
    "1384": "SIG_MIL_ESCALATION",         # Threaten conventional attack
    "1385": "SIG_MIL_ESCALATION",         # Threaten WMD
    "137":  "SIG_MIL_ESCALATION",         # Threaten violent repression
    "139":  "SIG_COERCIVE_BARGAINING",    # Give ultimatum
    "1312": "SIG_COERCIVE_BARGAINING",    # Threaten sanctions/embargo
    "1313": "SIG_NEGOTIATION_BREAKDOWN",  # Threaten to break relations
    # ── Violent repression (root 17 = ILLEGAL_COERCION → upgrade) ─
    "175":  "SIG_MIL_ESCALATION",         # Violent repression
    "1724": "SIG_MIL_ESCALATION",         # Impose martial law
    # ── De-escalation refusal (root 12 = NEG_BREAKDOWN → force) ──
    "1246": "SIG_MIL_ESCALATION",         # Refuse to de-escalate military
    "1212": "SIG_FORCE_POSTURE",          # Reject military cooperation
    # ── Sanctions as coercion (root 16 = NEG_BREAKDOWN → coercive) ─
    "163":  "SIG_COERCIVE_BARGAINING",    # Impose embargo/sanctions
    # ── Ceasefire / cooperative military sub-codes ────────────────
    "0871": "SIG_DIPLOMACY_ACTIVE",       # Declare ceasefire
    "0872": "SIG_DIPLOMACY_ACTIVE",       # Ease military blockade
    "0873": "SIG_DIPLOMACY_ACTIVE",       # Demobilize armed forces
    "0874": "SIG_DIPLOMACY_ACTIVE",       # Retreat or surrender
    "062":  "SIG_DIPLOMACY_ACTIVE",       # Cooperate militarily
    "057":  "SIG_DIPLOMACY_ACTIVE",       # Sign formal agreement
    "046":  "SIG_DIPLOMACY_ACTIVE",       # Engage in negotiation
    "074":  "SIG_DIPLOMACY_ACTIVE",       # Military protection/peacekeeping
}

# =====================================================================
# GDELT Bulk CSV Column Indices (v2.0 — no header row)
# =====================================================================
_COL_GLOBALEVENTID = 0
_COL_SQLDATE       = 1
_COL_ACTOR1CODE    = 5   # 3-char country code field
_COL_ACTOR1NAME    = 6
_COL_ACTOR1COUNTRY = 7
_COL_ACTOR1TYPE1   = 12  # Actor type code (GOV, MIL, REB, etc.)
_COL_ACTOR1TYPE2   = 13
_COL_ACTOR1TYPE3   = 14
_COL_ACTOR2CODE    = 15
_COL_ACTOR2NAME    = 16
_COL_ACTOR2COUNTRY = 17
_COL_ACTOR2TYPE1   = 22
_COL_ACTOR2TYPE2   = 23
_COL_ACTOR2TYPE3   = 24
_COL_EVENTCODE     = 26  # Full CAMEO code
_COL_EVENTROOTCODE = 27  # 2-digit root code
_COL_QUADCLASS     = 29  # 1-4
_COL_GOLDSTEIN     = 30
_COL_NUMMENTIONS   = 31
_COL_NUMSOURCES    = 32
_COL_AVGTONE       = 34
_COL_SOURCEURL     = 57

_MIN_COLS = 35  # must have at least through AvgTone

# GDELT last-update endpoint (15-min cadence)
_GDELT_LAST_UPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

# =====================================================================
# Evidence Strength Calibration
# =====================================================================
_STRENGTH_BASE  = 0.35
_STRENGTH_SCALE = 0.50
_STRENGTH_CAP   = 0.85


def _goldstein_to_strength(
    goldstein: Optional[float],
    event_code: str = "",
) -> float:
    """Convert Goldstein scale magnitude to evidence_strength [0.35, 0.85].

    When *goldstein* is None and an *event_code* is supplied, the official
    CAMEO Goldstein lookup table is consulted as a fallback.
    """
    if goldstein is None and event_code and _CAMEO_GOLDSTEIN:
        goldstein = _CAMEO_GOLDSTEIN.get(event_code)
    if goldstein is None:
        return 0.50
    magnitude = min(1.0, abs(float(goldstein)) / 10.0)
    return min(_STRENGTH_CAP, _STRENGTH_BASE + magnitude * _STRENGTH_SCALE)


def _tension_to_signal(tension: float, conflict_count: int, coop_count: int) -> str:
    """Derive a signal from aggregated tension data (fallback path)."""
    if tension >= 0.7 and conflict_count > 3:
        return "SIG_MIL_ESCALATION"
    if tension >= 0.55 and conflict_count > 0:
        return "SIG_DIP_HOSTILITY"
    if tension >= 0.4:
        return "SIG_COERCIVE_BARGAINING"
    if coop_count > conflict_count and tension < 0.35:
        return "SIG_DIPLOMACY_ACTIVE"
    if conflict_count > 0:
        return "SIG_INTERNAL_INSTABILITY"
    return ""  # no actionable signal


def _event_origin_id(event: Dict[str, Any]) -> str:
    """Generate content-based origin_id for echo deduplication."""
    parts = [
        str(event.get("id") or ""),
        str(event.get("event_code") or ""),
        str(event.get("actor1_country") or ""),
        str(event.get("actor2_country") or ""),
        str(event.get("date") or ""),
    ]
    raw = "gdelt_" + "_".join(parts)
    return f"gdelt_{hashlib.md5(raw.encode('utf-8', errors='ignore')).hexdigest()[:12]}"


# =====================================================================
# Sub-code signal resolution
# =====================================================================

def _resolve_signal(event_code: str) -> str:
    """Resolve CAMEO event code → SIG_* signal.

    Priority: full code → 3-digit prefix → 2-digit root code.
    Sub-codes override root when they represent a different signal category.
    """
    if not event_code:
        return ""
    # Try full event code (e.g., "1383")
    sig = CAMEO_SUBCODE_TO_SIGNAL.get(event_code)
    if sig:
        return sig
    # Try 3-digit prefix (e.g., "138")
    if len(event_code) >= 3:
        sig = CAMEO_SUBCODE_TO_SIGNAL.get(event_code[:3])
        if sig:
            return sig
    # Fall back to 2-digit root code
    root = event_code[:2] if len(event_code) >= 2 else event_code
    return CAMEO_TO_SIGNAL.get(root, "")


# =====================================================================
# Actor-type extraction & evidence boost
# =====================================================================

def _extract_actor_types(event: Dict[str, Any]) -> set:
    """Extract CAMEO actor type codes from an event dict.

    Checks 'actor1_types' / 'actor2_types' lists (populated by CSV parser).
    Returns a set of 3-char type codes, e.g. {'MIL', 'GOV'}.
    """
    types: set = set()
    for key in ("actor1_types", "actor2_types"):
        for t in event.get(key, []):
            code = str(t).strip().upper()
            if code:
                types.add(code)
    return types


def _actor_type_boost(actor_types: set, signal: str) -> float:
    """Compute evidence_strength multiplier based on actor types.

    Military actors boost escalation signals.
    Armed non-state actors boost instability signals.
    Government actors boost diplomatic/coercive signals.
    International actors boost credibility across all signals.

    Returns: multiplier in [1.0, 1.20].
    """
    if not actor_types:
        return 1.0

    boost = 1.0

    if actor_types & _MIL_TYPES and signal in (
        "SIG_MIL_ESCALATION", "SIG_FORCE_POSTURE",
    ):
        boost = max(boost, 1.15)

    if actor_types & _ARMED_TYPES and signal in (
        "SIG_INTERNAL_INSTABILITY", "SIG_MIL_ESCALATION",
    ):
        boost = max(boost, 1.12)

    if actor_types & _GOV_TYPES and signal in (
        "SIG_COERCIVE_BARGAINING", "SIG_DIPLOMACY_ACTIVE",
        "SIG_DIP_HOSTILITY", "SIG_NEGOTIATION_BREAKDOWN",
    ):
        boost = max(boost, 1.10)

    if actor_types & _INTL_TYPES:
        boost = max(boost, 1.08)

    return boost


def _event_description(event_code: str) -> str:
    """Return human-readable description for a CAMEO event code.

    Tries sub-code lookup first, then root label.
    """
    desc = _CAMEO_SUBCODES.get(event_code)
    if desc:
        return desc
    root = event_code[:2] if len(event_code) >= 2 else event_code
    return _CAMEO_ROOT_LABELS.get(root, "")


# =====================================================================
# GDELTSensorAdapter
# =====================================================================

class GDELTSensorAdapter:
    """
    Converts GDELT event data → observation dicts for the BeliefAccumulator.

    Operating modes (tried in order):
        1. **Live fetch** — download latest 15-min bulk CSV, parse events.
        2. **Tension history** — read data/tension_history.json, derive obs.
        3. **Manual injection** — call sense_from_events() with pre-parsed events.
        4. **Empty** — graceful degradation, return [].
    """

    def __init__(
        self,
        min_mentions: int = 1,
        max_events: int = 50,
        project_root: Optional[str] = None,
    ):
        self.min_mentions = min_mentions
        self.max_events = max_events
        self._project_root = project_root or os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    # -----------------------------------------------------------------
    # Primary entry point: sense()
    # -----------------------------------------------------------------

    def sense(
        self,
        countries: List[str],
        hours_back: int = 24,
        query_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query GDELT and return observation dicts.

        Tries live fetch first; falls back to tension_history.json.
        Returns [] if all paths fail.
        """
        countries_upper = [c.upper() for c in countries]

        # Mode 1: live bulk CSV
        events = self._fetch_live_events(countries_upper)
        if events:
            obs = self._events_to_observations(events)
            logger.info(
                "[GDELT-LIVE] %d events → %d observations (%s)",
                len(events), len(obs), ",".join(countries_upper),
            )
            return obs

        # Mode 2: tension_history.json fallback
        obs = self._observations_from_tension_history(countries_upper, query_date)
        if obs:
            logger.info(
                "[GDELT-CACHED] tension_history → %d observations (%s)",
                len(obs), ",".join(countries_upper),
            )
            return obs

        logger.info("[GDELT] No data available for %s", countries_upper)
        return []

    # -----------------------------------------------------------------
    # Mode 1: Live GDELT bulk CSV fetch
    # -----------------------------------------------------------------

    def _fetch_live_events(
        self,
        countries: List[str],
    ) -> List[Dict[str, Any]]:
        """Download latest 15-min GDELT CSV and parse relevant events."""
        try:
            import requests  # deferred — not required if fallback works
        except ImportError:
            logger.debug("[GDELT] requests not installed — skipping live fetch")
            return []

        try:
            resp = requests.get(_GDELT_LAST_UPDATE_URL, timeout=10)
            if resp.status_code != 200:
                return []
            csv_url = resp.text.strip().split("\n")[0].split()[-1]

            csv_resp = requests.get(csv_url, timeout=30)
            if csv_resp.status_code != 200:
                return []

            with zipfile.ZipFile(io.BytesIO(csv_resp.content)) as zf:
                fname = zf.namelist()[0]
                raw = zf.open(fname).read().decode("utf-8", errors="replace")

        except Exception as exc:
            logger.debug("[GDELT] Live fetch failed: %s", exc)
            return []

        return self._parse_gdelt_csv(raw, countries)

    def _parse_gdelt_csv(
        self,
        raw_csv: str,
        countries: List[str],
    ) -> List[Dict[str, Any]]:
        """Parse tab-delimited GDELT CSV into event dicts."""
        events: List[Dict[str, Any]] = []
        country_set = set(countries)
        reader = csv.reader(raw_csv.splitlines(), delimiter="\t")

        for row in reader:
            if len(row) < _MIN_COLS:
                continue

            actor1_country = (row[_COL_ACTOR1COUNTRY] or "").strip().upper()
            actor2_country = (row[_COL_ACTOR2COUNTRY] or "").strip().upper()

            # Must involve at least one target country
            if actor1_country not in country_set and actor2_country not in country_set:
                continue

            try:
                goldstein = float(row[_COL_GOLDSTEIN]) if row[_COL_GOLDSTEIN] else 0.0
                mentions = int(row[_COL_NUMMENTIONS]) if row[_COL_NUMMENTIONS] else 0
                avgtone = float(row[_COL_AVGTONE]) if row[_COL_AVGTONE] else 0.0
            except (ValueError, IndexError):
                continue

            event_code = (row[_COL_EVENTCODE] or "").strip()
            source_url = row[_COL_SOURCEURL] if len(row) > _COL_SOURCEURL else ""

            # Extract actor type codes (GOV, MIL, REB, etc.)
            a1_types = [
                (row[c] or "").strip().upper()
                for c in (_COL_ACTOR1TYPE1, _COL_ACTOR1TYPE2, _COL_ACTOR1TYPE3)
                if len(row) > c and row[c]
            ]
            a2_types = [
                (row[c] or "").strip().upper()
                for c in (_COL_ACTOR2TYPE1, _COL_ACTOR2TYPE2, _COL_ACTOR2TYPE3)
                if len(row) > c and row[c]
            ]

            events.append({
                "id": row[_COL_GLOBALEVENTID],
                "date": row[_COL_SQLDATE],
                "actor1": (row[_COL_ACTOR1NAME] or "").strip(),
                "actor1_country": actor1_country,
                "actor1_types": a1_types,
                "actor2": (row[_COL_ACTOR2NAME] or "").strip(),
                "actor2_country": actor2_country,
                "actor2_types": a2_types,
                "event_code": event_code,
                "event_description": _event_description(event_code),
                "goldstein": goldstein,
                "quad_class": (row[_COL_QUADCLASS] or "").strip(),
                "num_mentions": mentions,
                "num_sources": int(row[_COL_NUMSOURCES] or "0"),
                "avg_tone": avgtone,
                "source_url": source_url,
            })

        # Sort by mentions descending, cap at max_events
        events.sort(key=lambda e: e["num_mentions"], reverse=True)
        return events[: self.max_events]

    # -----------------------------------------------------------------
    # Mode 2: Tension history fallback
    # -----------------------------------------------------------------

    def _observations_from_tension_history(
        self,
        countries: List[str],
        query_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Read data/tension_history.json and derive observations."""
        tension_path = os.path.join(self._project_root, "data", "tension_history.json")
        if not os.path.exists(tension_path):
            return []

        try:
            with open(tension_path, "r", encoding="utf-8") as fh:
                history = json.load(fh)
        except Exception:
            return []

        observations: List[Dict[str, Any]] = []
        country_set = set(countries)

        # Use the most recent date entry (or query_date if provided)
        dates = sorted(history.keys(), reverse=True)
        if query_date and query_date in history:
            dates = [query_date]
        elif dates:
            dates = dates[:1]  # latest only
        else:
            return []

        for date_key in dates:
            date_data = history.get(date_key, {})
            for country_code, entries in date_data.items():
                if country_code not in country_set:
                    continue
                for entry in entries:
                    tension = float(entry.get("tension", 0.5))
                    conflict_count = int(entry.get("conflict_count", 0))
                    coop_count = int(entry.get("coop_count", 0))
                    actors = entry.get("major_actors", [])

                    signal = _tension_to_signal(tension, conflict_count, coop_count)
                    if not signal:
                        continue

                    evidence_strength = min(
                        _STRENGTH_CAP,
                        _STRENGTH_BASE + tension * _STRENGTH_SCALE,
                    )

                    actor_str = ", ".join(actors[:3]) if actors else country_code
                    excerpt = (
                        f"GDELT tension for {country_code}: {tension:.3f} "
                        f"(conflict={conflict_count}, coop={coop_count}). "
                        f"Key actors: {actor_str}"
                    )[:300]

                    origin_id = f"gdelt_tension_{country_code}_{date_key}_{entry.get('time', '00:00')}"

                    observations.append({
                        "type": "observation",
                        "signal": signal,
                        "source_type": "DATASET",
                        "date_source": "event_date",
                        "evidence_strength": round(evidence_strength, 4),
                        "corroboration": max(1, conflict_count + coop_count),
                        "keyword_hits": 1,
                        "origin_id": origin_id,
                        "source": "GDELT",
                        "url": "https://www.gdeltproject.org/",
                        "timestamp": f"{date_key}T{entry.get('time', '00:00')}:00Z",
                        "excerpt": excerpt,
                    })

        return observations

    # -----------------------------------------------------------------
    # Mode 3: Manual event injection (for tests / pre-fetched data)
    # -----------------------------------------------------------------

    def sense_from_events(
        self,
        events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Convert pre-parsed event dicts to observations.

        Each event dict should have: id, date, actor1, actor1_country,
        actor2, actor2_country, event_code, goldstein, num_mentions,
        quad_class, source_url.
        """
        return self._events_to_observations(events)

    # -----------------------------------------------------------------
    # Core: events → observations
    # -----------------------------------------------------------------

    def _events_to_observations(
        self,
        events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Convert GDELT event dicts → observation dicts.

        Uses sub-code signal resolution (CAMEO_SUBCODE_TO_SIGNAL) before
        falling back to root-code mapping.  Actor-type weighting boosts
        evidence_strength when military / armed / government actors are
        involved in signals matching their domain.
        """
        observations: List[Dict[str, Any]] = []
        seen_signals: Dict[str, int] = {}

        # Pre-count signal occurrences for corroboration
        for event in events[: self.max_events]:
            code = str(event.get("event_code") or "").strip()
            signal = _resolve_signal(code)
            if signal:
                seen_signals[signal] = seen_signals.get(signal, 0) + 1

        for event in events[: self.max_events]:
            mentions = int(event.get("num_mentions") or 0)
            if mentions < self.min_mentions:
                continue

            event_code = str(event.get("event_code") or "").strip()
            signal = _resolve_signal(event_code)
            if not signal:
                continue

            goldstein = event.get("goldstein")
            evidence_strength = _goldstein_to_strength(goldstein, event_code)

            # Actor-type boost (MIL → +15% for escalation, etc.)
            actor_types = _extract_actor_types(event)
            boost = _actor_type_boost(actor_types, signal)
            evidence_strength = min(_STRENGTH_CAP, evidence_strength * boost)

            event_date = event.get("date")
            timestamp = self._normalize_timestamp(event_date)

            actor1 = event.get("actor1", "")
            actor2 = event.get("actor2", "")
            description = _event_description(event_code)
            if not description:
                description = event.get("event_description", "")
            location = event.get("location", "")
            quad_class = event.get("quad_class", "")
            boost_tag = f" [actor-boost x{boost:.2f}]" if boost > 1.0 else ""
            excerpt = (
                f"GDELT: {actor1} → {actor2}: {description} "
                f"({quad_class}) at {location}. "
                f"Goldstein={goldstein}, mentions={mentions}{boost_tag}"
            )[:300]

            origin_id = _event_origin_id(event)
            corroboration = seen_signals.get(signal, 1)

            obs = {
                "type": "observation",
                "signal": signal,
                "source_type": "DATASET",
                "date_source": "event_date",
                "evidence_strength": round(evidence_strength, 4),
                "corroboration": min(20, corroboration),
                "keyword_hits": 1,
                "origin_id": origin_id,
                "source": "GDELT",
                "url": event.get("source_url", "https://www.gdeltproject.org/"),
                "timestamp": timestamp,
                "excerpt": excerpt,
            }
            observations.append(obs)

        return observations

    @staticmethod
    def _extract_root_code(event: Dict[str, Any]) -> str:
        """Extract 2-digit CAMEO root code from event_code."""
        code = str(event.get("event_code") or "").strip()
        if len(code) >= 2:
            return code[:2]
        return code

    @staticmethod
    def _normalize_timestamp(date_value: Any) -> str:
        """Convert GDELT date to ISO timestamp."""
        if not date_value:
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        date_str = str(date_value).strip()
        if date_str.isdigit() and len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}T00:00:00Z"
        if len(date_str) == 10 and date_str[4] == "-":
            return f"{date_str}T00:00:00Z"
        if "T" in date_str:
            return date_str if date_str.endswith("Z") else date_str + "Z"
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =====================================================================
# Module-level convenience
# =====================================================================

_default_adapter: Optional[GDELTSensorAdapter] = None


def get_gdelt_adapter(**kwargs) -> GDELTSensorAdapter:
    """Get or create the module-level GDELTSensorAdapter singleton."""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = GDELTSensorAdapter(**kwargs)
    return _default_adapter


def sense_gdelt(
    countries: List[str],
    hours_back: int = 24,
    query_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience: query GDELT and return observation dicts.

    Usage:
        from engine.Layer1_Collection.sensors.gdelt_sensor import sense_gdelt
        obs = sense_gdelt(["IND", "PAK"], hours_back=24)
    """
    return get_gdelt_adapter().sense(countries, hours_back, query_date)


__all__ = [
    "GDELTSensorAdapter",
    "get_gdelt_adapter",
    "sense_gdelt",
    "CAMEO_TO_SIGNAL",
    "CAMEO_SUBCODE_TO_SIGNAL",
    "DE_ESCALATION_SIGNALS",
]
