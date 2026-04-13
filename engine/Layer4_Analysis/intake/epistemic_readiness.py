"""
Epistemic Readiness Gate — Layer-4 pre-analysis evidence check.

This module decides whether the system has enough *epistemic* material
to attempt reasoning.  It does NOT judge confidence or correctness —
that is the Coordinator's internal safety-review responsibility.

The gate checks three things:
    1. Signal availability   — ≥2 distinct signal-type categories
    2. Evidence sufficiency  — ≥1 provenance-backed source or RAG document
    3. Contradiction flag    — high contradiction ratio → warning (not block)

Design rationale:
    A human analyst does not refuse to think because the scanner is broken.
    But they do refuse to write an assessment when they have *zero sources*.
    This gate models that behaviour.  Heavy epistemic checks (confidence
    thresholds, claim support, grounding) stay inside the Coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
MIN_SIGNAL_TYPE_CATEGORIES = 2   # need signals from ≥2 families
CONTRADICTION_WARNING_RATIO = 0.80  # >80% contradictory → warning (not block)


# Canonical signal-family prefixes.  A signal name like "SIG_MIL_ESCALATION"
# belongs to the "MIL" family.  We also accept plain names like "MILITARY".
_SIGNAL_FAMILY_PREFIXES = {
    "MIL": "MILITARY",
    "DIP": "DIPLOMATIC",
    "ECON": "ECONOMIC",
    "DOM": "DOMESTIC",
    "LEG": "LEGAL",
    "CYB": "CYBER",
    "POL": "POLITICAL",
    "MILITARY": "MILITARY",
    "DIPLOMATIC": "DIPLOMATIC",
    "ECONOMIC": "ECONOMIC",
    "DOMESTIC": "DOMESTIC",
    "LEGAL": "LEGAL",
    "CYBER": "CYBER",
    "POLITICAL": "POLITICAL",
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class EpistemicReadinessResult:
    ready: bool
    signal_types_found: int
    signal_families: List[str] = field(default_factory=list)
    evidence_backing: bool = False
    provenance_count: int = 0
    rag_document_count: int = 0
    observation_source_count: int = 0
    contradiction_ratio: float = 0.0
    warnings: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ready": self.ready,
            "signal_types_found": self.signal_types_found,
            "signal_families": list(self.signal_families),
            "evidence_backing": self.evidence_backing,
            "provenance_count": self.provenance_count,
            "rag_document_count": self.rag_document_count,
            "observation_source_count": self.observation_source_count,
            "contradiction_ratio": round(self.contradiction_ratio, 4),
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
        }


# ---------------------------------------------------------------------------
# Gate implementation
# ---------------------------------------------------------------------------
def check_epistemic_readiness(state_context: Any) -> EpistemicReadinessResult:
    """
    Lightweight pre-analysis gate.

    Returns ``ready=True`` when:
        • ≥2 distinct signal-type families are present, AND
        • ≥1 evidence-backing source exists (provenance, RAG doc, or observation).

    Contradiction among signals produces a *warning* but never blocks.
    """
    warnings: List[str] = []
    blockers: List[str] = []

    # ── 1. Signal availability ────────────────────────────────────────────
    families = _extract_signal_families(state_context)
    signal_types_found = len(families)
    if signal_types_found < MIN_SIGNAL_TYPE_CATEGORIES:
        blockers.append(
            f"Only {signal_types_found} signal type(s) available "
            f"(need ≥{MIN_SIGNAL_TYPE_CATEGORIES}). "
            "The system cannot reason without diverse signal input."
        )

    # ── 2. Evidence sufficiency ───────────────────────────────────────────
    provenance_count, rag_count, obs_source_count = _count_evidence(state_context)
    evidence_backing = (provenance_count >= 1 or rag_count >= 1 or obs_source_count >= 1)
    if not evidence_backing:
        blockers.append(
            "No evidence backing found (0 provenance entries, 0 RAG documents, "
            "0 observation sources). Cannot attempt analysis without any evidence."
        )

    # ── 3. Contradiction flag (warning only) ──────────────────────────────
    contradiction_ratio = _compute_contradiction_ratio(state_context)
    if contradiction_ratio > CONTRADICTION_WARNING_RATIO:
        warnings.append(
            f"High contradiction among signals ({contradiction_ratio:.0%}). "
            "Assessment may carry elevated uncertainty."
        )

    ready = (signal_types_found >= MIN_SIGNAL_TYPE_CATEGORIES and evidence_backing)

    return EpistemicReadinessResult(
        ready=ready,
        signal_types_found=signal_types_found,
        signal_families=sorted(families),
        evidence_backing=evidence_backing,
        provenance_count=provenance_count,
        rag_document_count=rag_count,
        observation_source_count=obs_source_count,
        contradiction_ratio=contradiction_ratio,
        warnings=warnings,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _extract_signal_families(state_context: Any) -> Set[str]:
    """Collect distinct signal families from beliefs + observed_signals."""
    families: Set[str] = set()

    # From signal_beliefs (list of dicts or objects)
    for belief in list(getattr(state_context, "signal_beliefs", []) or []):
        name = ""
        if isinstance(belief, dict):
            name = str(belief.get("signal", belief.get("name", ""))).upper()
        else:
            name = str(getattr(belief, "signal", getattr(belief, "name", ""))).upper()
        family = _classify_family(name)
        if family:
            families.add(family)

    # From observed_signals (set of signal names)
    for sig in set(getattr(state_context, "observed_signals", set()) or set()):
        family = _classify_family(str(sig).upper())
        if family:
            families.add(family)

    # From signal_confidence keys
    for key in dict(getattr(state_context, "signal_confidence", {}) or {}).keys():
        family = _classify_family(str(key).upper())
        if family:
            families.add(family)

    # Fallback: derive from dimensional context presence
    # If Layer-3 populated military/diplomatic/economic/domestic contexts,
    # those count as signal families even if no explicit signal names exist.
    _fallback_from_dimensions(state_context, families)

    return families


def _classify_family(signal_name: str) -> str:
    """Map a signal name to its canonical family, or '' if unknown."""
    if not signal_name:
        return ""
    # Try prefix match: SIG_MIL_ESCALATION → MIL → MILITARY
    parts = signal_name.replace("-", "_").split("_")
    for part in parts:
        part_clean = part.strip()
        if part_clean in _SIGNAL_FAMILY_PREFIXES:
            return _SIGNAL_FAMILY_PREFIXES[part_clean]
    # Try full-name match
    if signal_name in _SIGNAL_FAMILY_PREFIXES:
        return _SIGNAL_FAMILY_PREFIXES[signal_name]
    return ""


def _fallback_from_dimensions(state_context: Any, families: Set[str]) -> None:
    """
    If no explicit signal names yielded families, check whether
    dimensional context objects are populated with non-default values.
    """
    _DIM_MAP = {
        "military": "MILITARY",
        "diplomatic": "DIPLOMATIC",
        "economic": "ECONOMIC",
        "domestic": "DOMESTIC",
    }
    for attr, family in _DIM_MAP.items():
        ctx = getattr(state_context, attr, None)
        if ctx is None:
            continue
        # Check if any numeric field > 0  (non-default)
        for field_name in ("mobilization_level", "hostility_tone", "sanctions",
                           "economic_pressure", "unrest", "clash_history",
                           "exercises", "negotiations", "trade_dependency",
                           "regime_stability", "protests"):
            val = getattr(ctx, field_name, None)
            if val is not None:
                try:
                    if float(val) > 0.05:
                        families.add(family)
                        break
                except (TypeError, ValueError):
                    pass


def _count_evidence(state_context: Any) -> tuple:
    """Return (provenance_count, rag_document_count, observation_source_count)."""
    provenance_count = 0
    rag_count = 0
    obs_source_count = 0

    evidence_ctx = getattr(state_context, "evidence", None)
    if evidence_ctx is not None:
        # Provenance entries
        prov = getattr(evidence_ctx, "signal_provenance", {})
        if isinstance(prov, dict):
            for rows in prov.values():
                provenance_count += len(list(rows or []))
        # RAG documents
        rag_docs = getattr(evidence_ctx, "rag_documents", None)
        if rag_docs:
            rag_count = len(list(rag_docs))

    # Observation quality source_count
    obs_q = getattr(state_context, "observation_quality", None)
    if obs_q is not None:
        if isinstance(obs_q, dict):
            obs_source_count = int(obs_q.get("source_count", 0) or 0)
        else:
            obs_source_count = int(getattr(obs_q, "source_count", 0) or 0)

    return provenance_count, rag_count, obs_source_count


def _compute_contradiction_ratio(state_context: Any) -> float:
    """
    Estimate what fraction of signal beliefs are *contradictory*.

    A signal is considered contradictory when:
        - its belief is < 0.30  (weak/negative evidence for its hypothesis)
        - AND at least some signals have belief ≥ 0.50

    Returns 0.0 when there are fewer than 2 signals.
    """
    beliefs_raw = list(getattr(state_context, "signal_beliefs", []) or [])
    if len(beliefs_raw) < 2:
        return 0.0

    values: List[float] = []
    for b in beliefs_raw:
        if isinstance(b, dict):
            v = b.get("belief", b.get("value", 0.5))
        else:
            v = getattr(b, "belief", getattr(b, "value", 0.5))
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            values.append(0.5)

    if not values:
        return 0.0

    strong = sum(1 for v in values if v >= 0.50)
    weak = sum(1 for v in values if v < 0.30)

    if strong == 0:
        return 0.0  # no baseline to contradict

    return min(1.0, weak / len(values))


__all__ = [
    "EpistemicReadinessResult",
    "check_epistemic_readiness",
    "MIN_SIGNAL_TYPE_CATEGORIES",
    "CONTRADICTION_WARNING_RATIO",
]
