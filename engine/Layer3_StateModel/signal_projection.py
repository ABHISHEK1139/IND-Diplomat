"""
Signal Projection — the bridge from world-model to belief-state.
=================================================================

Converts Layer-3 ``StateContext`` telemetry into a ``Dict[str, ObservedSignal]``
that Layer-4's council can reason over probabilistically.

Before this module existed the pipeline had:

    StateContext  →  council reasoning

Now it has:

    StateContext  →  perception  →  belief signals  →  council reasoning

This is the missing "sensory cortex".

Design
------
1.  Read ``signal_beliefs`` (fuzzy membership already computed by
    ``SignalBeliefModel`` via ``triangular`` / ``trapezoidal`` functions).
2.  Read ``signal_confidence``, ``signal_evidence``, ``evidence.signal_provenance``
    for reliability and provenance.
3.  Compute composite confidence:
        ``confidence = membership × reliability × recency``
4.  Attach provenance sources and dimensional classification.
5.  Return ``Dict[str, ObservedSignal]`` — a structured belief set,
    NOT a flat ``Set[str]``.

This function **never** mutates the state_context.  It is a pure projection.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.observed_signal import ObservedSignal
from engine.Layer3_StateModel.evidence_support import compute_document_support
from engine.Layer3_StateModel.signal_registry import (
    canonicalize, SIGNAL_DIMENSION as _REGISTRY_DIM,
    ALIAS_TO_CANONICAL, DIMENSION_FLOORS, get_floor,
)

logger = logging.getLogger(__name__)


# ── Dimension classification ──────────────────────────────────────────
# Delegates to signal_registry for canonical tokens; keeps local overrides
# for any legacy tokens not yet in the registry.
_SIGNAL_DIMENSION: Dict[str, str] = dict(_REGISTRY_DIM)
# Add legacy aliases so dimension lookup works for un-canonicalized tokens
for _alias, _canon in ALIAS_TO_CANONICAL.items():
    if _alias not in _SIGNAL_DIMENSION and _canon in _REGISTRY_DIM:
        _SIGNAL_DIMENSION[_alias] = _REGISTRY_DIM[_canon]


# ── Namespace classification ──────────────────────────────────────────
# Signals known to _SIGNAL_DIMENSION are empirical (sensor-derived).
# Signals with source "LegalReasoner" or not in _SIGNAL_DIMENSION are legal.
_LEGAL_SOURCES = {"legalreasoner", "legal_reasoner", "legal"}


def _classify_namespace(signal: str, sources: list) -> str:
    """Determine whether a signal is empirical or legal."""
    # Explicit legal source → always legal
    for src in (sources or []):
        if str(src).lower().strip() in _LEGAL_SOURCES:
            return "legal"
    # Not in the empirical dimension table → legal/unknown
    if signal not in _SIGNAL_DIMENSION:
        return "legal"
    return "empirical"


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value or 0.0)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


# ── Temporal decay ────────────────────────────────────────────────────
# Different dimension types have different half-lives: military CAPABILITY
# signals decay fastest (a troop movement 6 months ago is stale), while
# COST signals (sanctions regimes) persist much longer.
_DECAY_LAMBDAS: Dict[str, float] = {
    "CAPABILITY": 0.008,     # half-life ~87 days
    "INTENT": 0.005,         # half-life ~139 days
    "STABILITY": 0.006,      # half-life ~116 days
    "COST": 0.001,           # half-life ~693 days (sanctions persist)
}


def _temporal_decay(event_date: datetime, dimension: str) -> float:
    """
    Exponential time-decay based on signal dimension.

    Returns a value in (0, 1] where 1.0 = just happened, decaying
    toward 0 as the event ages.  The decay rate depends on the
    dimension — CAPABILITY signals go stale fast, COST signals persist.
    """
    now = datetime.now(timezone.utc)
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)
    age_days = max(0, (now - event_date).days)
    lam = _DECAY_LAMBDAS.get(dimension, 0.004)
    return math.exp(-lam * age_days)


def _extract_most_recent_date(provenance_rows: List[Any]) -> Optional[datetime]:
    """Extract the most recent publication/event date from provenance entries."""
    best: Optional[datetime] = None
    for row in list(provenance_rows or []):
        if isinstance(row, dict):
            raw = row.get("date", row.get("publication_date", ""))
        else:
            raw = getattr(row, "date", getattr(row, "publication_date", ""))
        raw = str(raw or "").strip()
        if not raw:
            continue
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                     "%d/%m/%Y", "%Y"):
            try:
                dt = datetime.strptime(raw, fmt)
                if best is None or dt > best:
                    best = dt
                break
            except ValueError:
                continue
    return best


# ── Source URL lookup (mirrors state_provider's table) ────────────────
_SOURCE_URLS: Dict[str, str] = {
    "SIPRI": "https://www.sipri.org/",
    "GDELT": "https://www.gdeltproject.org/",
    "UCDP": "https://ucdp.uu.se/",
    "V-Dem": "https://www.v-dem.net/",
    "WorldBank": "https://data.worldbank.org/",
    "Sanctions": "https://www.sanctionsmap.eu/",
    "OFAC": "https://ofac.treasury.gov/",
    "Comtrade": "https://comtradeplus.un.org/",
    "ATOP": "https://atop-data.github.io/",
}


def _extract_source_names(provenance_rows: List[Any]) -> List[str]:
    """Extract deduplicated source names from provenance entries."""
    names: List[str] = []
    seen: set = set()
    for row in list(provenance_rows or []):
        if isinstance(row, dict):
            name = str(row.get("source_name", row.get("source", "")) or "").strip()
        else:
            name = str(getattr(row, "source_name", getattr(row, "source", "")) or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _extract_reliability(provenance_rows: List[Any]) -> float:
    """Compute average reliability from provenance entries."""
    scores: List[float] = []
    for row in list(provenance_rows or []):
        if isinstance(row, dict):
            val = row.get("reliability", row.get("confidence", None))
        else:
            val = getattr(row, "reliability", getattr(row, "confidence", None))
        if val is not None:
            scores.append(_clip01(_safe_float(val, 0.0)))
    if scores:
        return _clip01(sum(scores) / len(scores))
    return 0.5  # neutral default when no provenance info


def project_state_to_observed_signals(
    state_context: Any,
    retrieved_docs: Optional[list] = None,
) -> Dict[str, ObservedSignal]:
    """
    Convert a Layer-3 ``StateContext`` into structured belief signals.

    This is a **pure projection** — it does not mutate state_context.

    The function:
      1. Reads ``signal_beliefs`` (fuzzy membership from SignalBeliefModel).
      2. Reads ``signal_confidence`` as fallback confidence values.
      3. Reads provenance entries for source names and reliability.
      4. Reads ``temporal`` / ``meta`` for recency factor.
      5. Computes: ``confidence = membership × reliability × recency × evidence_support``
      6. Classifies each signal into a dimension.

    Parameters
    ----------
    state_context : Any
        Layer-3 StateContext object.
    retrieved_docs : list, optional
        RAG-retrieved documents.  When provided, each signal's confidence
        is modulated by documentary evidence support (boost or penalty).

    Returns
    -------
    Dict[str, ObservedSignal]
        Keyed by canonical signal name (e.g. ``SIG_FORCE_POSTURE``).
        Every signal with non-zero membership is included — there is
        NO binary threshold.  The council uses continuous belief strength.
    """
    projected: Dict[str, ObservedSignal] = {}

    if state_context is None:
        return projected

    # ── 1.  Gather raw signal beliefs ───────────────────────────────
    signal_beliefs = list(getattr(state_context, "signal_beliefs", []) or [])
    signal_confidence = dict(getattr(state_context, "signal_confidence", {}) or {})

    # ── 2.  Gather provenance data ──────────────────────────────────
    evidence_ctx = getattr(state_context, "evidence", None)
    signal_provenance: Dict[str, List[Any]] = {}
    if evidence_ctx is not None:
        raw_prov = getattr(evidence_ctx, "signal_provenance", {})
        if isinstance(raw_prov, dict):
            signal_provenance = dict(raw_prov)

    signal_evidence = dict(getattr(state_context, "signal_evidence", {}) or {})

    # ── 3.  Global recency factor ───────────────────────────────────
    temporal = getattr(state_context, "temporal", None)
    meta = getattr(state_context, "meta", None)

    global_recency = 0.5
    if temporal is not None:
        global_recency = _clip01(_safe_float(
            getattr(temporal, "stability", 0.5), 0.5
        ))
    elif meta is not None:
        global_recency = _clip01(_safe_float(
            getattr(meta, "temporal_stability",
                    getattr(meta, "time_recency", 0.5)),
            0.5,
        ))

    # Global meta reliability (source_consistency / data_confidence)
    global_reliability = 0.5
    if meta is not None:
        global_reliability = _clip01(_safe_float(
            getattr(meta, "source_consistency",
                    getattr(meta, "data_confidence", 0.5)),
            0.5
        ))

    # ── 4.  Process each signal belief ──────────────────────────────
    for belief_obj in signal_beliefs:
        signal = str(getattr(belief_obj, "signal", "") or "").strip().upper()
        if not signal:
            continue

        # Fuzzy membership — the core telemetry reading
        membership = _clip01(_safe_float(getattr(belief_obj, "belief", 0.0), 0.0))
        if membership <= 0.0:
            continue  # zero membership → no perception

        # Source agreement from the belief model
        source_agreement = _clip01(_safe_float(
            getattr(belief_obj, "source_agreement", global_reliability), global_reliability
        ))

        # Temporal stability from the belief model
        temporal_stability = _clip01(_safe_float(
            getattr(belief_obj, "temporal_stability", global_recency), global_recency
        ))

        # Provenance rows for this signal
        prov_rows = list(signal_provenance.get(signal, []) or [])
        ev_rows = list(signal_evidence.get(signal, []) or [])
        all_rows = prov_rows + ev_rows

        # Reliability from provenance (or fall back to belief model's source_agreement)
        prov_reliability = _extract_reliability(all_rows) if all_rows else source_agreement
        reliability = max(prov_reliability, source_agreement)

        # Dimension classification (needed for temporal decay rate)
        dimension = _SIGNAL_DIMENSION.get(signal, "UNKNOWN")

        # Recency: per-signal temporal decay from provenance dates.
        # Falls back to the belief model's temporal_stability if no date found.
        # Uses MAX of provenance-date decay and belief model's temporal_stability
        # so that a signal recently observed via OSINT is not penalised by old
        # dataset dates in provenance (e.g., SIPRI 2024 vs MoltBot today).
        event_date = _extract_most_recent_date(all_rows)
        if event_date is not None:
            recency = max(_temporal_decay(event_date, dimension), temporal_stability)
        else:
            recency = temporal_stability

        # Sources from provenance (must be computed before confidence formula)
        sources = _extract_source_names(all_rows)
        if not sources and signal in signal_confidence:
            # Fallback: if confidence exists but no provenance, mark as "derived"
            sources = ["derived"]

        # ── Composite confidence ────────────────────────────────────
        # Phase 2 Mathematical Expectation:
        # signal_confidence = source_reliability × extraction_quality
        # extraction_quality is conceptually mapped to membership here.
        ev_support = compute_document_support(signal, retrieved_docs or [])
        source_count = max(1, len(sources) if sources else 1)
        corroboration_boost = 1.0 + math.log(1.0 + source_count) * 0.3
        
        # extraction_quality defaults to membership. We check provenance rows
        # if any row overrides the extraction quality natively.
        extraction_quality = membership
        quality_scores = []
        for row in all_rows:
            if isinstance(row, dict) and "extraction_quality" in row:
                quality_scores.append(_clip01(_safe_float(row["extraction_quality"])))
            elif hasattr(row, "extraction_quality") and getattr(row, "extraction_quality") is not None:
                quality_scores.append(_clip01(_safe_float(getattr(row, "extraction_quality"))))
        if quality_scores:
            extraction_quality = sum(quality_scores) / len(quality_scores)
            
        raw_conf = reliability * extraction_quality * recency * ev_support * corroboration_boost
        # Fix 2: Apply dimension floor — prevents multiplicative crush
        dim_floor = DIMENSION_FLOORS.get(dimension, 0.10)
        confidence = _clip01(max(raw_conf, dim_floor) if extraction_quality > 0.05 else raw_conf)

        # Intensity = raw membership value (how "loud" the signal is)
        intensity = membership

        projected[signal] = ObservedSignal(
            name=signal,
            confidence=confidence,
            membership=membership,
            reliability=reliability,
            recency=recency,
            intensity=intensity,
            sources=sources,
            dimension=dimension,
            namespace=_classify_namespace(signal, sources),
        )

    # ── 5.  Include signals from signal_confidence not yet covered ──
    #    (These come from pressure-derived signals set by the coordinator
    #     or from legal/economic reasoning that extended observed_signals.)
    for token, conf_value in signal_confidence.items():
        sig = str(token or "").strip().upper()
        if not sig or sig in projected:
            continue
        conf = _clip01(_safe_float(conf_value, 0.0))
        if conf <= 0.0:
            continue

        prov_rows = list(signal_provenance.get(sig, []) or [])
        ev_rows = list(signal_evidence.get(sig, []) or [])
        all_rows = prov_rows + ev_rows
        sources = _extract_source_names(all_rows)
        if not sources:
            sources = ["derived"]

        dim = _SIGNAL_DIMENSION.get(sig, "UNKNOWN")
        event_date = _extract_most_recent_date(all_rows)
        recency = max(_temporal_decay(event_date, dim), global_recency) if event_date else global_recency

        projected[sig] = ObservedSignal(
            name=sig,
            confidence=conf,
            membership=conf,
            reliability=global_reliability,
            recency=recency,
            intensity=conf,
            sources=sources,
            dimension=dim,
            namespace=_classify_namespace(sig, sources),
        )

    # ── 6.  Also include legal/economic flags from observed_signals ──
    raw_observed = set(getattr(state_context, "observed_signals", set()) or set())
    for token in raw_observed:
        sig = str(token or "").strip().upper()
        if not sig or sig in projected:
            continue
        conf = _clip01(_safe_float(signal_confidence.get(sig, 0.55), 0.55))
        prov_rows = list(signal_provenance.get(sig, []) or [])
        ev_rows = list(signal_evidence.get(sig, []) or [])
        all_rows = prov_rows + ev_rows
        sources = _extract_source_names(all_rows)
        if not sources:
            sources = ["derived"]

        _mrd = _extract_most_recent_date(all_rows)
        _dim = _SIGNAL_DIMENSION.get(sig, "UNKNOWN")
        _ns = _classify_namespace(sig, sources)
        projected[sig] = ObservedSignal(
            name=sig,
            confidence=conf,
            membership=conf,
            reliability=_extract_reliability(all_rows) if all_rows else global_reliability,
            recency=max(_temporal_decay(_mrd, _dim), global_recency) if _mrd else global_recency,
            intensity=conf,
            sources=sources,
            dimension=_dim,
            namespace=_ns,
        )

    # ── Phase 4.2 + Phase 5: Adaptive weak-signal dampener ───────────
    # Suppress noise from very-low-confidence signals before they
    # can inflate dimension scores in downstream domain fusion.
    # Phase 5 expansion mode softens thresholds slightly so early-
    # warning signals (e.g. SIG_LOGISTICS_PREP at conf=0.09) are
    # not completely crushed during trajectory expansion.
    #
    # expansion_mode is injected by the caller via kwarg or defaults
    # to "NONE" (strict Phase 4 behavior).
    _expansion_mode = str(getattr(
        project_state_to_observed_signals, "_expansion_mode", "NONE"
    ) or "NONE").upper()

    if _expansion_mode == "HIGH":
        _low_thresh, _mid_thresh = 0.08, 0.13
        _low_mult, _mid_mult = 0.6, 0.8
    elif _expansion_mode == "MEDIUM":
        _low_thresh, _mid_thresh = 0.09, 0.14
        _low_mult, _mid_mult = 0.6, 0.8
    else:  # NONE — original strict Phase 4 behavior
        _low_thresh, _mid_thresh = 0.10, 0.15
        _low_mult, _mid_mult = 0.5, 0.7

    _dampened = 0
    for _sig_name, _obs in projected.items():
        if _obs.confidence < _low_thresh:
            _obs.membership *= _low_mult
            _dampened += 1
        elif _obs.confidence < _mid_thresh:
            _obs.membership *= _mid_mult
            _dampened += 1
    if _dampened:
        logger.info(
            "[SignalProjection] Phase 4.2: dampened membership for %d weak signal(s) "
            "(expansion=%s, thresholds=%.2f/%.2f)",
            _dampened, _expansion_mode, _low_thresh, _mid_thresh,
        )

    # ── Fix 1: CANONICALIZE + DEDUP — merge aliases into canonical tokens ──
    # This is the critical step that prevents 5 economic variants from
    # inflating cost_raw to 0.96.  Duplicates merge by keeping the
    # HIGHEST confidence variant (corroboration from multiple measurement
    # approaches should strengthen, not dilute).
    _canonical: Dict[str, ObservedSignal] = {}
    _merge_count = 0
    for _raw_name, _obs in projected.items():
        _canon = canonicalize(_raw_name)
        if _canon in _canonical:
            # Keep the one with higher confidence; merge source lists
            existing = _canonical[_canon]
            if _obs.confidence > existing.confidence:
                # Merge sources from the weaker signal
                merged_sources = list(existing.sources or [])
                for s in (_obs.sources or []):
                    if s not in merged_sources:
                        merged_sources.append(s)
                _obs.sources = merged_sources
                _obs.name = _canon
                _obs.dimension = _SIGNAL_DIMENSION.get(_canon, _obs.dimension)
                _canonical[_canon] = _obs
            else:
                # Keep existing, but merge sources from the duplicate
                for s in (_obs.sources or []):
                    if s not in existing.sources:
                        existing.sources.append(s)
            _merge_count += 1
        else:
            _obs.name = _canon
            _obs.dimension = _SIGNAL_DIMENSION.get(_canon, _obs.dimension)
            _canonical[_canon] = _obs
    if _merge_count:
        logger.info(
            "[SignalProjection] DEDUP: merged %d alias(es) → %d canonical signals (was %d)",
            _merge_count, len(_canonical), len(projected),
        )
    projected = _canonical

    # ── Phase-2: Purge non-empirical signals from projection output ───
    # Legal signals must NOT enter state memory.  They belong to
    # the narrative layer, not the empirical perception layer.
    _purged = {k: v for k, v in projected.items() if v.namespace == "empirical"}
    _n_purged = len(projected) - len(_purged)
    if _n_purged:
        logger.info(
            "[SignalProjection] Purged %d non-empirical signal(s) from projection output",
            _n_purged,
        )
    projected = _purged

    # ── Log the projection ──────────────────────────────────────────
    if projected:
        logger.info(
            "[SignalProjection] Projected %d belief signals from state:",
            len(projected),
        )
        for sig, obs in sorted(projected.items(), key=lambda x: -x[1].confidence):
            logger.info(
                "  %-32s conf=%.3f  memb=%.3f  rel=%.3f  rec=%.3f  dim=%-10s  ns=%-10s  src=%s",
                sig, obs.confidence, obs.membership, obs.reliability,
                obs.recency, obs.dimension, obs.namespace, ",".join(obs.sources[:3]),
            )
    else:
        logger.warning("[SignalProjection] No signals projected from state — perception empty.")

    return projected
