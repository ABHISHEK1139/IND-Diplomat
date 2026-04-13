"""
Epistemic Needs Assessment — "What am I missing and why?"
==========================================================

A real analyst doesn't just say "I don't know."
They say: "I can't assess military intent because my SIPRI data
is from 2024 and I have no recent satellite imagery."

This module gives Layer-4 that self-awareness.

After council deliberation, it examines each hypothesis against
the signal projection metadata (recency, evidence_support, confidence)
and produces *typed* information needs:

    STALE_DATA      → "SIPRI arms data is 87 days old.  Need data after 2025-06."
    MISSING_SOURCE  → "No diplomatic cables for IRN-ISR bilateral relations."
    LOW_COVERAGE    → "Only 1 of 8 INTENT signals has evidence backing."
    CONFLICTING     → "SIPRI says low, GDELT says high for SIG_MIL_ESCALATION."

These typed needs replace the generic signal-token list that the old
investigation loop used, enabling targeted collection instead of
blind re-queries.

Design rationale:
    The old flow:  missing_signals = ["SIG_MIL_ESCALATION"]
                    → PIR: "Iran SIG_MIL_ESCALATION"  (useless query)

    The new flow:  needs = [InformationNeed(
                        need_type=STALE_DATA,
                        signal_token="SIG_MIL_ESCALATION",
                        source_hint="sipri",
                        min_date="2025-06-01",
                        description="SIPRI arms transfer data is 87 days old"
                    )]
                    → PIR: "Iran arms transfers SIPRI 2025-2026"  (targeted)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger("epistemic_needs")


# =====================================================================
# InformationNeed — the typed gap request
# =====================================================================

class NeedType:
    STALE_DATA     = "stale_data"       # Data exists but is too old
    MISSING_SOURCE = "missing_source"   # No data from a needed source
    LOW_COVERAGE   = "low_coverage"     # Dimension has too few signals
    CONFLICTING    = "conflicting"      # Sources disagree
    WEAK_EVIDENCE  = "weak_evidence"    # No documents back this signal


class NeedPriority:
    CRITICAL  = "critical"    # Assessment unreliable without this
    IMPORTANT = "important"   # Significantly degrades accuracy
    DESIRABLE = "desirable"   # Would improve but not essential


# Signal→dimension mapping (subset — covers signals we compute)
_SIGNAL_DIMENSION: Dict[str, str] = {
    "SIG_MIL_ESCALATION":       "CAPABILITY",
    "SIG_FORCE_POSTURE":        "CAPABILITY",
    "SIG_MIL_MOBILIZATION":     "CAPABILITY",
    "SIG_CYBER_ACTIVITY":       "CAPABILITY",
    "SIG_DIP_HOSTILITY":        "INTENT",
    "SIG_ALLIANCE_ACTIVATION":  "INTENT",
    "SIG_ALLIANCE_SHIFT":       "INTENT",
    "SIG_COERCIVE_PRESSURE":    "INTENT",
    "SIG_COERCIVE_BARGAINING":  "INTENT",
    "SIG_RETALIATORY_THREAT":   "INTENT",
    "SIG_DETERRENCE_SIGNALING": "INTENT",
    "SIG_NEGOTIATION_BREAKDOWN":"INTENT",
    "SIG_INTERNAL_UNREST":      "STABILITY",
    "SIG_DOM_INTERNAL_INSTABILITY": "STABILITY",
    "SIG_ECO_SANCTIONS":        "COST",
    "SIG_ECO_SANCTIONS_ACTIVE": "COST",
    "SIG_ECO_PRESSURE_HIGH":    "COST",
    "SIG_ECO_DEPENDENCY":       "COST",
    "SIG_TRADE_DISRUPTION":     "COST",
    "SIG_WMD_RISK":             "CAPABILITY",
    "SIG_LEGAL_VIOLATION":      "INTENT",
}

# Source hints by dimension — which data sources help fill gaps
_DIMENSION_SOURCE_HINTS: Dict[str, List[str]] = {
    "CAPABILITY": ["sipri", "janes", "satellite_imagery", "defense_ministry"],
    "INTENT":     ["gdelt", "diplomatic_cables", "un_statements", "bilateral_treaty"],
    "STABILITY":  ["v_dem", "internal_news", "protest_tracker", "gdelt_domestic"],
    "COST":       ["world_bank", "un_comtrade", "imf", "sanctions_registry"],
}


@dataclass
class InformationNeed:
    """A typed request for specific information.

    This is what a minister produces when it cannot assess a dimension
    with sufficient confidence.  It tells the investigation loop WHAT
    to fetch, not just WHAT is missing.
    """
    need_type: str              # NeedType constant
    priority: str               # NeedPriority constant
    signal_token: str           # Which signal triggered this need
    dimension: str              # CAPABILITY | INTENT | STABILITY | COST
    minister: str               # Which minister identified this need
    description: str            # Human-readable: "Need recent SIPRI data for Iran"
    source_hint: str = ""       # Which data source would help: "sipri", "gdelt"
    min_date: str = ""          # "Need data after this date"
    country: str = ""           # Which country/entity
    current_recency: float = 1.0    # Current recency score (0=stale, 1=fresh)
    current_confidence: float = 0.0 # Current signal confidence
    current_evidence_support: float = 1.0  # Current evidence support multiplier
    confidence_impact: float = 0.0  # Estimated improvement if filled

    def to_dict(self) -> Dict[str, Any]:
        return {
            "need_type": self.need_type,
            "priority": self.priority,
            "signal_token": self.signal_token,
            "dimension": self.dimension,
            "minister": self.minister,
            "description": self.description,
            "source_hint": self.source_hint,
            "min_date": self.min_date,
            "country": self.country,
            "current_recency": round(self.current_recency, 4),
            "current_confidence": round(self.current_confidence, 4),
            "current_evidence_support": round(self.current_evidence_support, 4),
            "confidence_impact": round(self.confidence_impact, 4),
        }

    def to_pir_query(self) -> str:
        """Generate a targeted PIR query from this need."""
        parts = []
        if self.country:
            parts.append(self.country)
        if self.source_hint:
            parts.append(self.source_hint)
        # Add dimension-relevant search terms
        dim_terms = {
            "CAPABILITY": "military arms defense",
            "INTENT": "diplomatic statements intent signals",
            "STABILITY": "internal stability protests governance",
            "COST": "economic sanctions trade pressure",
        }
        parts.append(dim_terms.get(self.dimension, self.signal_token))
        if self.min_date:
            parts.append(f"after {self.min_date}")
        return " ".join(parts)


# =====================================================================
# Thresholds — when does a signal quality become a "need"?
# =====================================================================

RECENCY_STALE_THRESHOLD = 0.15      # Below this → STALE_DATA
RECENCY_AGING_THRESHOLD = 0.40      # Below this → IMPORTANT (not critical)
EVIDENCE_WEAK_THRESHOLD = 0.90      # Below 0.90 = no doc backing (0.85 default)
CONFIDENCE_LOW_THRESHOLD = 0.20     # Signal basically absent
COVERAGE_GAP_THRESHOLD = 0.30       # Dimension coverage below this → LOW_COVERAGE


# =====================================================================
# Core Assessment Function
# =====================================================================

def assess_epistemic_needs(
    hypotheses: Sequence[Any],
    projected_signals: Optional[Dict[str, Any]] = None,
    country: str = "",
) -> List[InformationNeed]:
    """
    Examine each hypothesis against signal projection metadata.

    For each predicted signal, checks:
    1. Recency   → Is the underlying data current?
    2. Evidence   → Do RAG documents corroborate this signal?
    3. Confidence → Is the signal actually observed?
    4. Coverage   → Does the dimension have enough signals?

    Returns a prioritized list of InformationNeed objects.
    """
    needs: List[InformationNeed] = []
    projected = dict(projected_signals or {})
    dimension_signals: Dict[str, List[float]] = {}  # dimension → [confidences]

    for hypothesis in list(hypotheses or []):
        minister = str(getattr(hypothesis, "minister", "unknown"))
        h_dimension = str(getattr(hypothesis, "dimension", "UNKNOWN")).upper()
        predicted = list(getattr(hypothesis, "predicted_signals", []) or [])
        missing = list(getattr(hypothesis, "missing_signals", []) or [])

        for token in predicted:
            token = str(token or "").strip().upper()
            if not token:
                continue

            # Get projection metadata for this signal
            proj = projected.get(token)
            recency = float(getattr(proj, "recency", 1.0) or 1.0) if proj else 1.0
            confidence = float(getattr(proj, "confidence", 0.0) or 0.0) if proj else 0.0
            evidence_support = float(getattr(proj, "evidence_support", 1.0) or 1.0) if proj else 1.0

            # Determine dimension
            dim = _SIGNAL_DIMENSION.get(token, h_dimension)

            # Track for coverage analysis
            dimension_signals.setdefault(dim, []).append(confidence)

            # Source hints for this dimension
            sources = _DIMENSION_SOURCE_HINTS.get(dim, [])
            source_hint = sources[0] if sources else ""

            # ── Check 1: STALE DATA ─────────────────────────────
            if recency < RECENCY_STALE_THRESHOLD:
                priority = NeedPriority.CRITICAL
                # Estimate date needed: if recency=0.034 with λ=0.008,
                # age ≈ -ln(0.034)/0.008 ≈ 420 days → data from ~Jan 2025
                min_date_str = ""
                try:
                    from datetime import timedelta
                    # Approximate: suggest data from 90 days ago
                    cutoff = datetime.now() - timedelta(days=90)
                    min_date_str = cutoff.strftime("%Y-%m-%d")
                except Exception:
                    pass

                needs.append(InformationNeed(
                    need_type=NeedType.STALE_DATA,
                    priority=priority,
                    signal_token=token,
                    dimension=dim,
                    minister=minister,
                    description=(
                        f"{token} data is stale (recency={recency:.3f}). "
                        f"Need fresh {source_hint or dim} data."
                    ),
                    source_hint=source_hint,
                    min_date=min_date_str,
                    country=country,
                    current_recency=recency,
                    current_confidence=confidence,
                    current_evidence_support=evidence_support,
                    confidence_impact=min(0.5, (1.0 - recency) * 0.6),
                ))

            elif recency < RECENCY_AGING_THRESHOLD:
                needs.append(InformationNeed(
                    need_type=NeedType.STALE_DATA,
                    priority=NeedPriority.IMPORTANT,
                    signal_token=token,
                    dimension=dim,
                    minister=minister,
                    description=(
                        f"{token} data is aging (recency={recency:.3f}). "
                        f"Fresher {source_hint or dim} data would improve accuracy."
                    ),
                    source_hint=source_hint,
                    country=country,
                    current_recency=recency,
                    current_confidence=confidence,
                    confidence_impact=min(0.3, (1.0 - recency) * 0.4),
                ))

            # ── Check 2: WEAK EVIDENCE (no document backing) ────
            if evidence_support <= EVIDENCE_WEAK_THRESHOLD and confidence > 0.1:
                needs.append(InformationNeed(
                    need_type=NeedType.WEAK_EVIDENCE,
                    priority=NeedPriority.IMPORTANT,
                    signal_token=token,
                    dimension=dim,
                    minister=minister,
                    description=(
                        f"{token} has no document corroboration "
                        f"(evidence_support={evidence_support:.2f}). "
                        f"Need {source_hint or dim} documents."
                    ),
                    source_hint=source_hint,
                    country=country,
                    current_evidence_support=evidence_support,
                    current_confidence=confidence,
                    confidence_impact=0.15,
                ))

            # ── Check 3: LOW CONFIDENCE (signal barely exists) ──
            if confidence < CONFIDENCE_LOW_THRESHOLD and token in missing:
                needs.append(InformationNeed(
                    need_type=NeedType.MISSING_SOURCE,
                    priority=NeedPriority.CRITICAL if dim in ("INTENT", "CAPABILITY") else NeedPriority.IMPORTANT,
                    signal_token=token,
                    dimension=dim,
                    minister=minister,
                    description=(
                        f"{token} effectively absent (confidence={confidence:.3f}). "
                        f"No source data feeds this signal. "
                        f"Need {source_hint or dim} collection."
                    ),
                    source_hint=source_hint,
                    country=country,
                    current_confidence=confidence,
                    confidence_impact=0.3,
                ))

    # ── Check 4: DIMENSION-LEVEL COVERAGE GAPS ──────────────────
    for dim, confs in dimension_signals.items():
        if not confs:
            continue
        avg_conf = sum(confs) / len(confs)
        if avg_conf < COVERAGE_GAP_THRESHOLD and len(confs) > 0:
            sources = _DIMENSION_SOURCE_HINTS.get(dim, [])
            needs.append(InformationNeed(
                need_type=NeedType.LOW_COVERAGE,
                priority=NeedPriority.CRITICAL,
                signal_token=f"DIMENSION_{dim}",
                dimension=dim,
                minister="coordinator",
                description=(
                    f"{dim} dimension has low overall coverage "
                    f"(avg confidence={avg_conf:.3f} across {len(confs)} signals). "
                    f"Need broad {dim.lower()} data collection."
                ),
                source_hint=", ".join(sources[:2]),
                country=country,
                current_confidence=avg_conf,
                confidence_impact=0.4,
            ))

    # Deduplicate by (signal_token, need_type) — keep highest priority
    _PRIORITY_RANK = {NeedPriority.CRITICAL: 0, NeedPriority.IMPORTANT: 1, NeedPriority.DESIRABLE: 2}
    seen: Dict[tuple, InformationNeed] = {}
    for need in needs:
        key = (need.signal_token, need.need_type)
        if key not in seen:
            seen[key] = need
        else:
            existing_rank = _PRIORITY_RANK.get(seen[key].priority, 99)
            new_rank = _PRIORITY_RANK.get(need.priority, 99)
            if new_rank < existing_rank:
                seen[key] = need

    deduped = sorted(
        seen.values(),
        key=lambda n: (_PRIORITY_RANK.get(n.priority, 99), -n.confidence_impact),
    )

    return deduped


def log_epistemic_needs(needs: List[InformationNeed]) -> None:
    """Log needs in the style of an analyst's information request memo."""
    if not needs:
        logger.info("[EPISTEMIC SELF-ASSESSMENT] All dimensions adequately covered.")
        return

    critical = [n for n in needs if n.priority == NeedPriority.CRITICAL]
    important = [n for n in needs if n.priority == NeedPriority.IMPORTANT]

    logger.info(
        "[EPISTEMIC SELF-ASSESSMENT] %d information needs identified "
        "(%d CRITICAL, %d IMPORTANT)",
        len(needs), len(critical), len(important),
    )

    for i, need in enumerate(needs[:10], 1):  # Log top 10
        logger.info(
            "  NEED-%d [%s] %s | %s → %s",
            i,
            need.priority.upper(),
            need.need_type,
            need.signal_token,
            need.description,
        )


def needs_to_pir_queries(
    needs: List[InformationNeed],
    max_queries: int = 5,
) -> List[str]:
    """Convert top-priority needs into targeted PIR query strings."""
    queries: List[str] = []
    seen = set()
    for need in needs[:max_queries]:
        q = need.to_pir_query()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)
    return queries


def needs_to_investigation_meta(
    needs: List[InformationNeed],
) -> Dict[str, Any]:
    """Convert needs list into metadata dict for the investigation phase."""
    return {
        "total_needs": len(needs),
        "critical_needs": len([n for n in needs if n.priority == NeedPriority.CRITICAL]),
        "need_types": list(set(n.need_type for n in needs)),
        "affected_dimensions": list(set(n.dimension for n in needs)),
        "top_needs": [n.to_dict() for n in needs[:5]],
        "pir_queries": needs_to_pir_queries(needs),
    }


__all__ = [
    "InformationNeed",
    "NeedType",
    "NeedPriority",
    "assess_epistemic_needs",
    "log_epistemic_needs",
    "needs_to_pir_queries",
    "needs_to_investigation_meta",
]
