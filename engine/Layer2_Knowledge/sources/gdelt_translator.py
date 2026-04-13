"""
GDELT Translator
================
Converts raw GDELT event records into semantic EventSignals.
Computes tension scores based on Goldstein Scale and AvgTone.
"""

from statistics import mean
from typing import Any, Dict, List

from .base import BaseTranslator
from ..signals.base import EventSignal
from ..source_registry import source_registry

# Import full CAMEO tables from the canonical sensor config.
try:
    from engine.Layer1_Collection.sensors.cameo_config import (
        CAMEO_EVENT_CODES,
        CAMEO_EVENT_ROOT_CODES,
        CAMEO_GOLDSTEIN,
    )
except (ImportError, ModuleNotFoundError):
    CAMEO_EVENT_CODES = {}
    CAMEO_EVENT_ROOT_CODES = {}
    CAMEO_GOLDSTEIN = {}


# ── Semantic label tables ──────────────────────────────────────────────
# Root codes → lowercase analytical labels (stable across all consumers).
_ROOT_SEMANTIC: Dict[str, str] = {
    "01": "public statement",
    "02": "appeal",
    "03": "intent to cooperate",
    "04": "consultation",
    "05": "diplomatic cooperation",
    "06": "material cooperation",
    "07": "aid",
    "08": "yield",
    "09": "investigation",
    "10": "demand",
    "11": "disapproval",
    "12": "rejection",
    "13": "threat",
    "14": "protest",
    "15": "force posture",
    "16": "reduce relations",
    "17": "coercion",
    "18": "assault",
    "19": "armed clash",
    "20": "mass violence",
}

# Sub-code overrides where the specific code carries a narrower meaning
# than the root category.
_SUBCODE_SEMANTIC: Dict[str, str] = {
    "057": "sign agreement",
    "1384": "military threat",
    "1383": "military threat",
    "1385": "military threat",
    "163": "sanctions",
    "196": "fight",
}

# Analytical dimensions — maps root codes to the strategic pressure axis
# they most strongly influence.
CAMEO_ANALYTICAL_DIMENSION: Dict[str, str] = {
    "01": "INTENT",       "02": "INTENT",        "03": "INTENT",
    "04": "INTENT",       "05": "INTENT",        "06": "CAPABILITY",
    "07": "CAPABILITY",   "08": "PRESSURE",      "09": "INSTABILITY",
    "10": "PRESSURE",     "11": "PRESSURE",      "12": "PRESSURE",
    "13": "INTENT",       "14": "INSTABILITY",   "15": "CAPABILITY",
    "16": "PRESSURE",     "17": "PRESSURE",      "18": "CAPABILITY",
    "19": "CAPABILITY",   "20": "INSTABILITY",
}


def classify_cameo_event_code(event_code: Any) -> str:
    """
    Return a stable, lowercase semantic label for a CAMEO event code.

    Resolution order:
      1. Sub-code override table  (e.g. "057" → "sign agreement")
      2. Root-code semantic table  (e.g. "05"  → "diplomatic cooperation")
      3. ``"unknown"``
    """
    code = str(event_code or "").strip()
    if not code:
        return "unknown"

    # 1. Exact sub-code override
    if code in _SUBCODE_SEMANTIC:
        return _SUBCODE_SEMANTIC[code]

    # 2. Root-code semantic label
    root = code[:2]
    return _ROOT_SEMANTIC.get(root, "unknown")


class GDELTTranslator(BaseTranslator):
    """Translates raw GDELT event data into high-level EventSignals."""

    def translate(self, records: List[Dict[str, Any]]) -> EventSignal:
        if not records:
            return EventSignal(
                source="GDELT",
                confidence=0.0,
                timestamp="",
                tension_score=0.5,
                goldstein_score=0.0,
                conflict_events=0,
                cooperation_events=0,
                major_actors=[],
                top_themes=[],
            )

        goldstein_scores = []
        conflict_count = 0
        cooperation_count = 0
        actors: Dict[str, int] = {}

        for record in records:
            try:
                goldstein = float(record.get("GoldsteinScale", 0.0) or 0.0)
            except (TypeError, ValueError):
                goldstein = 0.0
            goldstein_scores.append(goldstein)

            if goldstein < -1.0:
                conflict_count += 1
            elif goldstein > 1.0:
                cooperation_count += 1

            actor1 = record.get("Actor1Name")
            actor2 = record.get("Actor2Name")
            if actor1:
                actors[actor1] = actors.get(actor1, 0) + 1
            if actor2:
                actors[actor2] = actors.get(actor2, 0) + 1

        avg_goldstein = mean(goldstein_scores) if goldstein_scores else 0.0

        # Goldstein of -10 -> tension 1.0, +10 -> tension 0.0
        raw_tension = 1.0 - ((avg_goldstein + 10.0) / 20.0)
        tension_score = max(0.0, min(1.0, raw_tension))

        top_actors = [name for name, _ in sorted(actors.items(), key=lambda item: item[1], reverse=True)[:5]]

        timestamp = records[0].get("SQLDATE", "") or records[0].get("Day", "")

        return EventSignal(
            source="GDELT",
            confidence=source_registry.get_trust("gdelt"),
            timestamp=str(timestamp),
            tension_score=round(tension_score, 4),
            goldstein_score=round(avg_goldstein, 4),
            conflict_events=conflict_count,
            cooperation_events=cooperation_count,
            major_actors=top_actors,
            top_themes=[],
        )

    def classify_event_code(self, event_code: Any) -> str:
        """Expose CAMEO translation for validation tests and diagnostics."""
        return classify_cameo_event_code(event_code)
