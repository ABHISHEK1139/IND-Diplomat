"""
Priority Intelligence Requirement (PIR) — Typed Collection Tasks
================================================================

A real intelligence analyst never says:
    "I want more information."

They say:
    "We lack confirmation of adversary force mobilization in sector X."

This module defines the PIR — the ONLY object that the investigation
phase produces.  A PIR is NOT a search query.  It is a typed measurement
request with:

    1. dimension     — which analytical dimension needs evidence
    2. signal        — which signal's uncertainty triggered this
    3. collection    — which collection modality can resolve it
    4. priority      — how urgently the assessment needs this
    5. reason        — structured belief-gap justification

The system can never generate free-text questions.
It can only decide WHAT MEASUREMENT IT NEEDS.

Collection Modalities (closed set — no free text allowed):
    IMINT           — Imagery intelligence (satellite, aerial)
    SIGINT          — Signals intelligence (comms intercepts)
    OSINT_EVENTS    — Structured event databases (GDELT, ACLED)
    OSINT_SOCIAL    — Social unrest monitoring (protest trackers)
    DIPLOMATIC_RPT  — Diplomatic reporting (embassy cables, UN)
    TRADE_FLOW      — Economic/trade flow monitoring (Comtrade, OFAC)
    LEGAL_CORPUS    — Legal instrument monitoring (treaties, UNSCR)
    SIPRI_ARMS      — Arms transfer databases (SIPRI)
    HUMINT          — Human intelligence source reporting
    CYBER_INTEL     — Cyber threat intelligence feeds
    V_DEM           — Governance/regime quality (V-Dem)

Design principle:
    The council decides WHAT it doesn't know.
    The PIR decides HOW to fill the gap.
    The collection system decides WHERE to look.

    No LLM is involved at any point.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("intelligence.pir")


# =====================================================================
# Collection Modalities — a CLOSED set, never free text
# =====================================================================

class CollectionModality(str, Enum):
    """
    The closed set of information-gathering modalities.

    Each modality corresponds to a specific type of sensor, database,
    or structured feed — never a search engine or LLM query.
    """
    IMINT          = "IMINT"           # Satellite/aerial imagery
    SIGINT         = "SIGINT"          # Communications intercepts
    OSINT_EVENTS   = "OSINT_EVENTS"    # Structured event feeds (GDELT, ACLED)
    OSINT_SOCIAL   = "OSINT_SOCIAL"    # Social/protest monitoring
    DIPLOMATIC_RPT = "DIPLOMATIC_RPT"  # Diplomatic cables/reporting
    TRADE_FLOW     = "TRADE_FLOW"      # Economic/trade data (Comtrade, OFAC)
    LEGAL_CORPUS   = "LEGAL_CORPUS"    # Treaty/UNSCR monitoring
    SIPRI_ARMS     = "SIPRI_ARMS"      # Arms transfer databases
    HUMINT         = "HUMINT"          # Human source reporting
    CYBER_INTEL    = "CYBER_INTEL"     # Cyber threat intelligence
    V_DEM          = "V_DEM"           # Governance quality (V-Dem)


class PIRPriority(str, Enum):
    """How urgently the assessment needs this collection."""
    CRITICAL  = "CRITICAL"    # Assessment unreliable without this
    HIGH      = "HIGH"        # Significantly affects confidence
    ROUTINE   = "ROUTINE"     # Would improve but not essential


# =====================================================================
# PIR — the typed collection task
# =====================================================================

@dataclass
class PIR:
    """
    Priority Intelligence Requirement.

    This is the ONLY output of the investigation planning phase.
    It is NOT a search query, NOT a question, NOT free text.
    It is a structured measurement request.

    The system says:  "Signal X has recency 0.034 from SIPRI 2024-12-31.
                       I need SIPRI_ARMS collection for dimension CAPABILITY."

    NOT:  "Find news about Iran military."
    """
    dimension: str                  # CAPABILITY | INTENT | STABILITY | COST
    signal: str                     # Which signal's uncertainty triggered this
    collection: CollectionModality  # Which sensor/feed to task
    priority: PIRPriority           # CRITICAL | HIGH | ROUTINE
    reason: str                     # Structured justification (never free text query)

    # Metadata for the collection planner
    country: str = ""
    current_confidence: float = 0.0     # How confident we are now
    current_recency: float = 1.0        # How fresh the data is
    confidence_gap: float = 0.0         # How much improvement is possible
    min_date: str = ""                  # Earliest acceptable data date
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "signal": self.signal,
            "collection": self.collection.value,
            "priority": self.priority.value,
            "reason": self.reason,
            "country": self.country,
            "current_confidence": round(self.current_confidence, 4),
            "current_recency": round(self.current_recency, 4),
            "confidence_gap": round(self.confidence_gap, 4),
            "min_date": self.min_date,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"PIR({self.priority.value} | {self.collection.value} | "
            f"{self.signal} → {self.dimension} | "
            f"conf={self.current_confidence:.3f} rec={self.current_recency:.3f})"
        )


# =====================================================================
# Signal → Collection Modality Map (THE authority)
# =====================================================================
# This replaces SIGNAL_SEARCH_MAP, SIGNAL_COLLECTION_MAP, and
# to_pir_query() — all of which generated free-text search strings.
#
# The rule:  signal → modality, not signal → "search string"
# =====================================================================

SIGNAL_COLLECTION_MODALITY: Dict[str, List[CollectionModality]] = {
    # CAPABILITY signals → what sensors can measure them
    "SIG_MIL_ESCALATION":       [CollectionModality.SIPRI_ARMS, CollectionModality.IMINT, CollectionModality.OSINT_EVENTS],
    "SIG_FORCE_POSTURE":        [CollectionModality.IMINT, CollectionModality.SIPRI_ARMS, CollectionModality.SIGINT],
    "SIG_MIL_MOBILIZATION":     [CollectionModality.IMINT, CollectionModality.OSINT_EVENTS, CollectionModality.SIGINT],
    "SIG_LOGISTICS_PREP":       [CollectionModality.TRADE_FLOW, CollectionModality.IMINT],
    "SIG_LOGISTICS_SURGE":      [CollectionModality.TRADE_FLOW, CollectionModality.IMINT],
    "SIG_CYBER_ACTIVITY":       [CollectionModality.CYBER_INTEL, CollectionModality.SIGINT],
    "SIG_CYBER_PREPARATION":    [CollectionModality.CYBER_INTEL, CollectionModality.SIGINT],
    "SIG_WMD_RISK":             [CollectionModality.IMINT, CollectionModality.SIGINT, CollectionModality.SIPRI_ARMS],
    "SIG_DECEPTION_ACTIVITY":   [CollectionModality.SIGINT, CollectionModality.IMINT, CollectionModality.OSINT_EVENTS],

    # INTENT signals → what sensors can measure them
    "SIG_DIP_HOSTILITY":        [CollectionModality.DIPLOMATIC_RPT, CollectionModality.OSINT_EVENTS],
    "SIG_DIP_HOSTILE_RHETORIC":  [CollectionModality.DIPLOMATIC_RPT, CollectionModality.OSINT_EVENTS],
    "SIG_ALLIANCE_ACTIVATION":  [CollectionModality.DIPLOMATIC_RPT, CollectionModality.LEGAL_CORPUS],
    "SIG_ALLIANCE_SHIFT":       [CollectionModality.DIPLOMATIC_RPT, CollectionModality.LEGAL_CORPUS],
    "SIG_NEGOTIATION_BREAKDOWN":[CollectionModality.DIPLOMATIC_RPT],
    "SIG_COERCIVE_PRESSURE":    [CollectionModality.LEGAL_CORPUS, CollectionModality.DIPLOMATIC_RPT],
    "SIG_COERCIVE_BARGAINING":  [CollectionModality.DIPLOMATIC_RPT, CollectionModality.OSINT_EVENTS],
    "SIG_RETALIATORY_THREAT":   [CollectionModality.DIPLOMATIC_RPT, CollectionModality.SIGINT],
    "SIG_DETERRENCE_SIGNALING": [CollectionModality.IMINT, CollectionModality.DIPLOMATIC_RPT, CollectionModality.SIGINT],
    "SIG_LEGAL_VIOLATION":      [CollectionModality.LEGAL_CORPUS],

    # STABILITY signals → what sensors can measure them
    "SIG_INTERNAL_INSTABILITY":     [CollectionModality.OSINT_SOCIAL, CollectionModality.V_DEM],
    "SIG_INTERNAL_UNREST":          [CollectionModality.OSINT_SOCIAL, CollectionModality.V_DEM],
    "SIG_DOM_INTERNAL_INSTABILITY": [CollectionModality.OSINT_SOCIAL, CollectionModality.V_DEM],

    # COST signals → what sensors can measure them
    "SIG_ECO_SANCTIONS":        [CollectionModality.TRADE_FLOW, CollectionModality.LEGAL_CORPUS],
    "SIG_ECO_SANCTIONS_ACTIVE": [CollectionModality.TRADE_FLOW, CollectionModality.LEGAL_CORPUS],
    "SIG_ECO_PRESSURE_HIGH":    [CollectionModality.TRADE_FLOW],
    "SIG_ECON_PRESSURE":        [CollectionModality.TRADE_FLOW],
    "SIG_ECONOMIC_PRESSURE":    [CollectionModality.TRADE_FLOW],
    "SIG_ECO_DEPENDENCY":       [CollectionModality.TRADE_FLOW],
    "SIG_TRADE_DISRUPTION":     [CollectionModality.TRADE_FLOW],
    "SIG_SANCTIONS_ACTIVE":     [CollectionModality.TRADE_FLOW, CollectionModality.LEGAL_CORPUS],
}


# =====================================================================
# Belief Gap Detection — "I believe something but lack evidence"
# =====================================================================

@dataclass
class BeliefGap:
    """
    A minister-level belief gap: high weight + low coverage.

    This is REAL analytical curiosity — not LLM curiosity.
    The system believes something is important but cannot confirm it.
    """
    minister: str
    dimension: str
    weight: float       # How important the system thinks this is
    coverage: float     # How much evidence supports it
    gap_severity: float # weight - coverage (higher = more urgent)
    signals: List[str] = field(default_factory=list)  # Associated signals

    def to_dict(self) -> Dict[str, Any]:
        return {
            "minister": self.minister,
            "dimension": self.dimension,
            "weight": round(self.weight, 4),
            "coverage": round(self.coverage, 4),
            "gap_severity": round(self.gap_severity, 4),
            "signals": list(self.signals),
        }


def detect_belief_gaps(
    hypotheses: List[Any],
    weight_threshold: float = 0.50,
    coverage_ceiling: float = 0.35,
) -> List[BeliefGap]:
    """
    Detect belief gaps: the system believes something important but lacks evidence.

    A gap exists when:
        hypothesis.weight >= weight_threshold  (system thinks this matters)
        AND
        hypothesis.coverage <= coverage_ceiling (system can't confirm it)

    This is the ONLY trigger for investigation — not missing signals,
    not low confidence, not LLM curiosity.

    Returns gaps sorted by severity (most urgent first).
    """
    gaps: List[BeliefGap] = []

    for h in list(hypotheses or []):
        weight = float(getattr(h, "weight", 0.0) or 0.0)
        coverage = float(getattr(h, "coverage", 0.0) or 0.0)
        minister = str(getattr(h, "minister", "unknown"))
        dimension = str(getattr(h, "dimension", "UNKNOWN")).upper()
        signals = list(getattr(h, "predicted_signals", []) or [])

        if weight >= weight_threshold and coverage <= coverage_ceiling:
            severity = weight - coverage
            gaps.append(BeliefGap(
                minister=minister,
                dimension=dimension,
                weight=weight,
                coverage=coverage,
                gap_severity=severity,
                signals=signals,
            ))

    gaps.sort(key=lambda g: g.gap_severity, reverse=True)
    return gaps


# =====================================================================
# Gap → PIR Conversion (the closed-loop bridge)
# =====================================================================

def gaps_to_pirs(
    gaps: List[BeliefGap],
    projected_signals: Optional[Dict[str, Any]] = None,
    country: str = "",
    max_pirs: int = 10,
) -> List[PIR]:
    """
    Convert belief gaps into Priority Intelligence Requirements.

    For each gap:
      1. Identify which signals need measurement
      2. Look up the collection modality (IMINT, DIPLOMATIC_RPT, etc.)
      3. Determine priority from gap severity
      4. Build a structured PIR — no free text, no search strings

    The PIR tells the collection system WHAT sensor to task,
    not WHAT text to search for.
    """
    pirs: List[PIR] = []
    seen: set = set()
    projected = dict(projected_signals or {})

    for gap in gaps:
        for signal in gap.signals:
            token = str(signal or "").strip().upper()
            if not token or token in seen:
                continue
            seen.add(token)

            # Look up collection modalities
            modalities = SIGNAL_COLLECTION_MODALITY.get(token)
            if not modalities:
                continue

            # Get signal metadata from projection
            proj = projected.get(token)
            recency = float(getattr(proj, "recency", 1.0) or 1.0) if proj else 1.0
            confidence = float(getattr(proj, "confidence", 0.0) or 0.0) if proj else 0.0

            # Determine priority from gap severity + signal confidence
            if gap.gap_severity > 0.5 or confidence < 0.05:
                priority = PIRPriority.CRITICAL
            elif gap.gap_severity > 0.3:
                priority = PIRPriority.HIGH
            else:
                priority = PIRPriority.ROUTINE

            # Compute minimum acceptable date from recency
            min_date = ""
            if recency < 0.15:
                try:
                    from datetime import timedelta
                    cutoff = datetime.now() - timedelta(days=90)
                    min_date = cutoff.strftime("%Y-%m-%d")
                except Exception:
                    pass

            # Build structured reason — NOT a search query
            reason = (
                f"{gap.dimension} uncertainty: {token} has "
                f"confidence={confidence:.3f}, recency={recency:.3f}. "
                f"Minister '{gap.minister}' weight={gap.weight:.3f} "
                f"but coverage={gap.coverage:.3f}."
            )

            # Issue PIR for the PRIMARY modality
            pir = PIR(
                dimension=gap.dimension,
                signal=token,
                collection=modalities[0],  # Primary modality
                priority=priority,
                reason=reason,
                country=country,
                current_confidence=confidence,
                current_recency=recency,
                confidence_gap=gap.gap_severity,
                min_date=min_date,
            )
            pirs.append(pir)

            if len(pirs) >= max_pirs:
                return pirs

    return pirs


def log_pirs(pirs: List[PIR]) -> None:
    """Log PIRs in the style of an intelligence collection plan."""
    if not pirs:
        logger.info("[COLLECTION PLAN] No PIRs issued — belief gaps adequately covered.")
        return

    critical = sum(1 for p in pirs if p.priority == PIRPriority.CRITICAL)
    high = sum(1 for p in pirs if p.priority == PIRPriority.HIGH)

    logger.info(
        "[COLLECTION PLAN] %d PIRs issued (%d CRITICAL, %d HIGH)",
        len(pirs), critical, high,
    )

    # Group by collection modality for display
    for i, pir in enumerate(pirs[:10], 1):
        logger.info(
            "  PIR-%d [%s] %s → %s | signal=%s | conf=%.3f rec=%.3f",
            i, pir.priority.value, pir.collection.value,
            pir.dimension, pir.signal,
            pir.current_confidence, pir.current_recency,
        )


# =====================================================================
# Collection Plan — the aggregate investigation instruction set
# =====================================================================

@dataclass
class CollectionPlan:
    """
    The complete set of PIRs for one investigation cycle.

    This is what gets passed to the collection system.
    It contains ONLY typed PIRs — never free text, never search queries.
    """
    pirs: List[PIR] = field(default_factory=list)
    belief_gaps: List[BeliefGap] = field(default_factory=list)
    country: str = ""
    cycle: int = 0

    @property
    def has_critical(self) -> bool:
        return any(p.priority == PIRPriority.CRITICAL for p in self.pirs)

    @property
    def modalities_needed(self) -> List[str]:
        """Unique collection modalities required."""
        return sorted(set(p.collection.value for p in self.pirs))

    @property
    def signals_targeted(self) -> List[str]:
        """Which signals we're trying to fill."""
        return [p.signal for p in self.pirs]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pir_count": len(self.pirs),
            "critical_count": sum(1 for p in self.pirs if p.priority == PIRPriority.CRITICAL),
            "belief_gaps": [g.to_dict() for g in self.belief_gaps],
            "modalities_needed": self.modalities_needed,
            "signals_targeted": self.signals_targeted,
            "pirs": [p.to_dict() for p in self.pirs],
            "country": self.country,
            "cycle": self.cycle,
        }


def build_collection_plan(
    hypotheses: List[Any],
    projected_signals: Optional[Dict[str, Any]] = None,
    country: str = "",
    cycle: int = 0,
) -> CollectionPlan:
    """
    Full closed-loop collection planning:
        belief gaps → PIRs → collection plan

    This is the SINGLE entry point for investigation planning.
    It replaces:
        - epistemic_needs.to_pir_query()     (free text)
        - pir_generator.generate_pirs()       (search strings)
        - SIGNAL_COLLECTION_MAP              (search strings)
    """
    gaps = detect_belief_gaps(hypotheses)
    pirs = gaps_to_pirs(gaps, projected_signals, country)
    log_pirs(pirs)

    return CollectionPlan(
        pirs=pirs,
        belief_gaps=gaps,
        country=country,
        cycle=cycle,
    )


__all__ = [
    "PIR",
    "PIRPriority",
    "CollectionModality",
    "SIGNAL_COLLECTION_MODALITY",
    "BeliefGap",
    "CollectionPlan",
    "detect_belief_gaps",
    "gaps_to_pirs",
    "log_pirs",
    "build_collection_plan",
]
