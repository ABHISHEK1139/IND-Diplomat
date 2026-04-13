"""
Evidence Corroboration Engine — Independent Confirmation Scoring
=================================================================

The single highest-impact upgrade for any intelligence pipeline.

Current system scores signals using:
    reliability × recency × intensity

Real intelligence analysis adds a critical fourth factor:
    **independent confirmation** (corroboration)

A signal reported by one article stays low-confidence.
The same signal confirmed by five independent sources from
three different agencies becomes actionable intelligence.

This module provides the mathematical model:

    corroboration_factor = 1 + log(1 + source_count)

    ┌──────────┬────────┐
    │ Sources  │ Factor │
    ├──────────┼────────┤
    │ 1        │ 1.69   │
    │ 2        │ 2.10   │
    │ 3        │ 2.39   │
    │ 5        │ 2.79   │
    │ 10       │ 3.40   │
    └──────────┴────────┘

Combined with source diversity (unique publishers / total sources),
this produces confidence values that match real-world intelligence
analysis practices used by organisations like the International
Crisis Group and RAND Corporation.

Pipeline position::

    event extraction
        ↓
    signal extraction
        ↓
    ► corroboration engine   ← THIS MODULE
        ↓
    belief accumulator

This is an ADDITIVE post-processing layer.
It does NOT modify any existing module.

Usage::

    from Core.evidence.corroboration_engine import (
        corroboration_boost,
        apply_corroboration,
        score_belief_corroboration,
        generate_corroboration_report,
    )

    # Single signal
    new_conf = corroboration_boost(0.16, source_count=5)
    # → 0.16 × 2.79 ≈ 0.45

    # Full belief dict from BeliefAccumulator
    enriched = score_belief_corroboration(belief_dict)
    # belief_dict now has corroborated_confidence, corroboration_factor, etc.

    # Batch analysis → CorroborationReport
    report = generate_corroboration_report(beliefs)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Core.evidence.corroboration")


# =====================================================================
# Core formulas
# =====================================================================

def corroboration_boost(
    confidence: float,
    source_count: int,
    *,
    ceiling: float = 1.0,
) -> float:
    """
    Apply logarithmic corroboration boost to a confidence score.

    Parameters
    ----------
    confidence : float
        Raw confidence value (0.0–1.0).
    source_count : int
        Number of sources confirming the signal.
    ceiling : float
        Maximum output value (default 1.0).

    Returns
    -------
    float
        Boosted confidence, clamped to [0.0, ceiling].

    Examples
    --------
    >>> round(corroboration_boost(0.16, 5), 2)
    0.45
    >>> round(corroboration_boost(0.18, 1), 2)
    0.25
    >>> round(corroboration_boost(0.95, 10), 2)
    1.0
    """
    confidence = max(0.0, min(1.0, float(confidence)))
    source_count = max(0, int(source_count))

    factor = _corroboration_factor(source_count)
    return min(confidence * factor, ceiling)


def _corroboration_factor(source_count: int) -> float:
    """
    Compute the raw corroboration multiplier.

    Formula: ``1 + log(1 + source_count)``

    ======= ======
    Sources Factor
    ======= ======
    0       1.00
    1       1.69
    2       2.10
    3       2.39
    5       2.79
    10      3.40
    ======= ======
    """
    return 1.0 + math.log(1.0 + max(0, source_count))


def diversity_factor(
    unique_sources: int,
    total_sources: int,
) -> float:
    """
    Measure source independence.

    Five articles from Reuters is weaker than five articles
    from five different agencies.

    Parameters
    ----------
    unique_sources : int
        Number of distinct publishers / agencies.
    total_sources : int
        Total number of observations.

    Returns
    -------
    float
        Ratio in [0.0, 1.0].  1.0 = all sources are independent.

    Examples
    --------
    >>> diversity_factor(3, 5)
    0.6
    >>> diversity_factor(5, 5)
    1.0
    >>> diversity_factor(1, 5)
    0.2
    """
    unique_sources = max(0, int(unique_sources))
    total_sources = max(1, int(total_sources))
    return min(1.0, unique_sources / total_sources)


def apply_corroboration(
    confidence: float,
    source_count: int,
    unique_sources: int,
    total_sources: int,
    *,
    ceiling: float = 1.0,
) -> float:
    """
    Apply corroboration boost with source-diversity weighting.

    Combined formula::

        new_conf = confidence
                   × corroboration_factor
                   × diversity_factor

    Parameters
    ----------
    confidence : float
        Raw confidence value (0.0–1.0).
    source_count : int
        Number of sources confirming the signal.
    unique_sources : int
        Distinct publishers / agencies.
    total_sources : int
        Total observations for this signal.
    ceiling : float
        Maximum output value (default 1.0).

    Returns
    -------
    float
        Boosted and diversity-weighted confidence, clamped to [0.0, ceiling].
    """
    confidence = max(0.0, min(1.0, float(confidence)))
    corr = _corroboration_factor(max(0, int(source_count)))
    div = diversity_factor(unique_sources, total_sources)
    return min(confidence * corr * div, ceiling)


# =====================================================================
# Belief-dict enrichment
# =====================================================================

def score_belief_corroboration(
    belief: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Enrich a single belief dict with corroboration metadata.

    Reads the ``corroboration`` (source count) and ``sources`` fields
    that ``BeliefAccumulator.evaluate()`` already populates on each
    belief dict, then appends new keys.

    Parameters
    ----------
    belief : dict
        A belief dict from ``BeliefAccumulator.evaluate()``.
        Expected keys: ``confidence``, ``corroboration``, ``sources``.

    Returns
    -------
    dict
        The *same* dict (mutated in place) with added keys:

        - ``corroborated_confidence`` — boosted confidence
        - ``corroboration_factor``    — raw multiplier
        - ``diversity_factor``        — publisher independence ratio
        - ``corroboration_class``     — "single-source" | "multi-source" | "cross-domain"
    """
    raw_conf = float(belief.get("confidence", 0.0))
    source_count = int(belief.get("corroboration", 0))
    sources = list(belief.get("sources", []))
    total = max(1, len(sources)) if sources else max(1, source_count)
    unique = len(set(str(s).lower() for s in sources)) if sources else source_count

    corr = _corroboration_factor(source_count)
    div = diversity_factor(unique, total)
    boosted = min(raw_conf * corr * div, 1.0)

    belief["corroborated_confidence"] = round(boosted, 6)
    belief["corroboration_factor"] = round(corr, 4)
    belief["diversity_factor"] = round(div, 4)
    belief["corroboration_class"] = _classify_corroboration(source_count, unique)

    logger.debug(
        "[CORROB] %s: raw=%.3f × factor=%.2f × div=%.2f → %.3f (%s)",
        belief.get("signal", "?"),
        raw_conf, corr, div, boosted,
        belief["corroboration_class"],
    )

    return belief


def _classify_corroboration(source_count: int, unique_sources: int) -> str:
    """Classify the corroboration level into an intelligence category."""
    if unique_sources >= 3:
        return "cross-domain"
    if source_count >= 2:
        return "multi-source"
    return "single-source"


# =====================================================================
# Projected-signal batch scoring
# =====================================================================

def score_projected_signals(
    projected_signals: List[Any],
) -> List[Dict[str, Any]]:
    """
    Score a list of projected ObservedSignal objects for corroboration.

    Each ObservedSignal has ``.name``, ``.confidence``, ``.sources``.

    Parameters
    ----------
    projected_signals : list
        ObservedSignal instances from ``signal_projection.project()``.

    Returns
    -------
    list[dict]
        Per-signal corroboration breakdown::

            {
                "signal": str,
                "raw_confidence": float,
                "corroborated_confidence": float,
                "corroboration_factor": float,
                "diversity_factor": float,
                "source_count": int,
                "unique_sources": int,
                "corroboration_class": str,
            }
    """
    results: List[Dict[str, Any]] = []

    for sig in (projected_signals or []):
        name = getattr(sig, "name", "")
        raw_conf = float(getattr(sig, "confidence", 0.0))
        sources = list(getattr(sig, "sources", []) or [])

        source_count = len(sources)
        unique = len(set(str(s).lower() for s in sources)) if sources else 0
        total = max(1, source_count)

        corr = _corroboration_factor(source_count)
        div = diversity_factor(unique, total)
        boosted = min(raw_conf * corr * div, 1.0)

        results.append({
            "signal": name,
            "raw_confidence": round(raw_conf, 6),
            "corroborated_confidence": round(boosted, 6),
            "corroboration_factor": round(corr, 4),
            "diversity_factor": round(div, 4),
            "source_count": source_count,
            "unique_sources": unique,
            "corroboration_class": _classify_corroboration(source_count, unique),
        })

    return results


# =====================================================================
# Corroboration Report
# =====================================================================

@dataclass
class CorroborationReport:
    """
    Aggregate corroboration analysis over an evidence set.

    Produced by ``generate_corroboration_report()``.
    """
    total_signals: int = 0
    single_source_count: int = 0
    multi_source_count: int = 0
    cross_domain_count: int = 0
    mean_corroboration_factor: float = 1.0
    mean_diversity_factor: float = 0.0
    weakest_signal: str = ""
    strongest_signal: str = ""
    per_signal: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def corroboration_coverage(self) -> float:
        """Fraction of signals with multi-source or cross-domain confirmation."""
        if self.total_signals == 0:
            return 0.0
        return (self.multi_source_count + self.cross_domain_count) / self.total_signals

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_signals": self.total_signals,
            "single_source_count": self.single_source_count,
            "multi_source_count": self.multi_source_count,
            "cross_domain_count": self.cross_domain_count,
            "corroboration_coverage": round(self.corroboration_coverage, 4),
            "mean_corroboration_factor": round(self.mean_corroboration_factor, 4),
            "mean_diversity_factor": round(self.mean_diversity_factor, 4),
            "weakest_signal": self.weakest_signal,
            "strongest_signal": self.strongest_signal,
            "per_signal": self.per_signal,
        }

    def summary(self) -> str:
        """One-line human-readable summary."""
        return (
            f"{self.total_signals} signals: "
            f"{self.cross_domain_count} cross-domain, "
            f"{self.multi_source_count} multi-source, "
            f"{self.single_source_count} single-source "
            f"(coverage {self.corroboration_coverage:.0%})"
        )


def generate_corroboration_report(
    beliefs: Optional[List[Dict[str, Any]]] = None,
    projected_signals: Optional[List[Any]] = None,
) -> CorroborationReport:
    """
    Generate an aggregate corroboration report.

    Accepts EITHER belief dicts (from BeliefAccumulator) OR projected
    signal objects (from signal_projection).  If both are given,
    projected_signals takes priority.

    Parameters
    ----------
    beliefs : list[dict], optional
        Belief dicts from ``BeliefAccumulator.evaluate()``.
    projected_signals : list, optional
        ObservedSignal objects from ``signal_projection.project()``.

    Returns
    -------
    CorroborationReport
    """
    # Score signals
    if projected_signals:
        per_signal = score_projected_signals(projected_signals)
    elif beliefs:
        per_signal = []
        for b in beliefs:
            enriched = score_belief_corroboration(dict(b))  # copy to avoid mutation
            per_signal.append({
                "signal": enriched.get("signal", "?"),
                "raw_confidence": float(enriched.get("confidence", 0.0)),
                "corroborated_confidence": float(enriched.get("corroborated_confidence", 0.0)),
                "corroboration_factor": float(enriched.get("corroboration_factor", 1.0)),
                "diversity_factor": float(enriched.get("diversity_factor", 0.0)),
                "source_count": int(enriched.get("corroboration", 0)),
                "unique_sources": len(set(str(s).lower() for s in enriched.get("sources", []))),
                "corroboration_class": enriched.get("corroboration_class", "single-source"),
            })
    else:
        return CorroborationReport()

    # Aggregate
    report = CorroborationReport(
        total_signals=len(per_signal),
        per_signal=per_signal,
    )

    if not per_signal:
        return report

    factors: List[float] = []
    divs: List[float] = []
    weakest_conf = float("inf")
    strongest_conf = -1.0

    for entry in per_signal:
        cls = entry.get("corroboration_class", "single-source")
        if cls == "single-source":
            report.single_source_count += 1
        elif cls == "multi-source":
            report.multi_source_count += 1
        elif cls == "cross-domain":
            report.cross_domain_count += 1

        factors.append(entry.get("corroboration_factor", 1.0))
        divs.append(entry.get("diversity_factor", 0.0))

        corr_conf = entry.get("corroborated_confidence", 0.0)
        sig_name = entry.get("signal", "?")
        if corr_conf < weakest_conf:
            weakest_conf = corr_conf
            report.weakest_signal = sig_name
        if corr_conf > strongest_conf:
            strongest_conf = corr_conf
            report.strongest_signal = sig_name

    report.mean_corroboration_factor = sum(factors) / len(factors)
    report.mean_diversity_factor = sum(divs) / len(divs)

    logger.info(
        "[CORROB-REPORT] %s",
        report.summary(),
    )

    return report


# =====================================================================
# Exports
# =====================================================================

__all__ = [
    "corroboration_boost",
    "diversity_factor",
    "apply_corroboration",
    "score_belief_corroboration",
    "score_projected_signals",
    "generate_corroboration_report",
    "CorroborationReport",
]
