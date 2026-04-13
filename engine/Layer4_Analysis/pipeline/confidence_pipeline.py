"""
Confidence Pipeline — Multi-factor confidence scoring
======================================================
Extracted from coordinator._synthesize_decision (lines 2140–2400).

Computes weighted_confidence through:
  1. Base confidence (weighted sum of sensor, verification, logic, meta, doc)
  2. Evidence multiplier (diverse sourcing)
  3. Dimensional balance multiplier
  4. Temporal support multiplier
  5. Calibration bonus (Phase 6)
  6. Cross-theater forecast adjustment (Phase 7)
  7. Sensor anchoring bias correction
  8. Gap & contradiction penalties
  9. Corroboration boost
  10. Council adjustment / shadow mode gate

All results are stored on ``session`` attributes — the function
returns the final ``weighted_confidence`` float.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def compute_weighted_confidence(
    session: Any,
    sensor_score: float,
    projected_list: List[Any],
    dimensions: dict,
    driver_score: float,
) -> float:
    """Compute the pipeline's final weighted confidence.

    Parameters
    ----------
    session : CouncilSession
        Mutable — intermediate results are stored as attributes.
    sensor_score : float
        SRE escalation score (or net_score fallback).
    projected_list : list
        Projected signal objects from state_context.
    dimensions : dict
        ``{CAPABILITY, INTENT, STABILITY, COST}`` coverage dict.
    driver_score : float
        Weighted dimension driver score.

    Returns
    -------
    float
        Clamped ``weighted_confidence`` in [0.05, 0.95].
    """

    # ── Base scores ────────────────────────────────────────────────
    v_score = max(0.0, min(1.0, float(getattr(session, "verification_score", 0.0) or 0.0)))
    l_score = max(0.0, min(1.0, float(getattr(session, "logic_score", 0.0) or 0.0)))

    # Fix 7: Compute meta_conf from actual evidence quality instead of
    # hardcoded 0.5.  Uses source diversity, temporal freshness, and
    # corroboration to produce a genuine quality metric.
    _proj_list_safe = list(projected_list or [])
    _unique_source_names = set()
    _fresh_count = 0
    _corroborated_count = 0
    for _sig in _proj_list_safe:
        _src = getattr(_sig, "sources", []) or []
        for _s in _src:
            _unique_source_names.add(str(_s).lower())
        if len(_src) >= 2:
            _corroborated_count += 1
        if getattr(_sig, "recency", 0.0) > 0.7:
            _fresh_count += 1
    _n_signals = max(1, len(_proj_list_safe))
    _source_diversity = min(1.0, len(_unique_source_names) / 8.0)  # 8 sources = full diversity
    _temporal_freshness = _fresh_count / _n_signals
    _corroboration_score = _corroborated_count / _n_signals
    meta_conf = max(0.15, min(0.85,
        0.30 * _source_diversity + 0.30 * _temporal_freshness + 0.40 * _corroboration_score
    ))
    logger.info(
        "[CONF-FIX7] meta_conf=%.3f (src_div=%.2f fresh=%.2f corrob=%.2f)",
        meta_conf, _source_diversity, _temporal_freshness, _corroboration_score,
    )

    # Pipeline firewall — doc_conf deferred to post-gate.
    doc_conf = 0.0
    session.rag_evidence = []
    logger.info("[SYNTHESIS] doc_conf=0.0 (pipeline firewall — RAG deferred to post-gate)")

    rt_penalty = float(getattr(session, "red_team_confidence_penalty", 0.0) or 0.0)

    # ── Step 1: Base confidence (weighted sum minus red-team) ──────
    # Fix 7: Redistrubuted weights to active components only.
    # Removed v_score/l_score/doc_conf (always 0) from formula.
    # Added driver_score (dimension coverage) as genuine multi-factor input.
    # v_score and l_score are added back as bonuses when they become active.
    _driver = max(0.0, min(1.0, float(driver_score or 0.0)))
    base_confidence = max(0.0, min(1.0,
        0.50 * float(sensor_score) +
        0.35 * meta_conf +
        0.15 * _driver
        + 0.05 * v_score     # bonus when verification module activates
        + 0.05 * l_score     # bonus when logic module activates
        - rt_penalty
    ))

    # ── Step 2: Evidence multiplier ───────────────────────────────
    # Phase 8 fix: count unique signal .name attributes (not .source which
    # doesn't exist on projected signal objects).
    _num_sources = len(set(
        str(getattr(s, "name", ""))
        for s in projected_list
        if str(getattr(s, "name", "")).strip()
    )) if projected_list else 0
    _evidence_multiplier = 1.10 if _num_sources >= 4 else 1.00
    logger.info("[CONF-FIX1] evidence_sources=%d -> evidence_mult=%.2f",
                _num_sources, _evidence_multiplier)

    # ── Step 3: Dimensional balance multiplier ────────────────────
    _sre_dom = getattr(session, "sre_domains", None) or {}
    _active_dims = 0
    if _sre_dom:
        _active_dims = sum(1 for d in ("capability", "intent", "stability", "cost")
                           if _sre_dom.get(d, 0.0) > 0.25)
    if _active_dims >= 3:
        _dim_multiplier = 1.05
    elif _active_dims <= 1:
        _dim_multiplier = 0.95
    else:
        _dim_multiplier = 1.00
    logger.info("[CONF-FIX1] active_dims=%d -> dim_mult=%.2f",
                _active_dims, _dim_multiplier)

    # ── Step 4: Temporal support multiplier ───────────────────────
    _sre_inp = getattr(session, "sre_input", None)
    _esc_patterns = int(getattr(_sre_inp, "escalation_patterns", 0)) if _sre_inp else 0
    _spk_count = int(getattr(_sre_inp, "spike_count", 0)) if _sre_inp else 0
    _temporal_multiplier = 1.00
    if _spk_count >= 2:
        _temporal_multiplier = 1.08
    elif _esc_patterns >= 2:
        _temporal_multiplier = 1.05
    logger.info("[CONF-FIX1] esc_patterns=%d spike_count=%d -> temporal_mult=%.2f",
                _esc_patterns, _spk_count, _temporal_multiplier)

    # ── Multiplicative combination ────────────────────────────────
    weighted_confidence = base_confidence * _evidence_multiplier * _dim_multiplier * _temporal_multiplier
    weighted_confidence = max(0.0, min(1.0, weighted_confidence))
    logger.info("[CONF-FIX1] base=%.3f x ev=%.2f x dim=%.2f x temp=%.2f -> conf=%.3f",
                base_confidence, _evidence_multiplier, _dim_multiplier,
                _temporal_multiplier, weighted_confidence)

    # ── Phase 6: Calibration bonus ────────────────────────────────
    try:
        from engine.Layer6_Learning.confidence_recalibrator import calibration_bonus
        _p6_cal_country = str(getattr(session, "learning_country", None) or "")
        _p6_multiplier = calibration_bonus(_p6_cal_country or None)
        if _p6_multiplier < 1.0:
            weighted_confidence = max(0.0, weighted_confidence * _p6_multiplier)
            logger.info(
                "[PHASE6] Calibration bonus: ×%.4f → conf=%.3f",
                _p6_multiplier, weighted_confidence,
            )
        session.learning_confidence_multiplier = _p6_multiplier
    except Exception as _p6_cal_exc:
        logger.warning("[PHASE6] Calibration bonus failed: %s", _p6_cal_exc)
        session.learning_confidence_multiplier = 1.0

    # ── Phase 7: Cross-theater forecast adjustment ────────────────
    try:
        from Config.config import ENABLE_GLOBAL_MODEL as _P7_ON2
        if _P7_ON2:
            from engine.Layer7_GlobalModel.cross_theater_forecaster import (
                adjusted_probability, global_risk_summary, global_black_swan,
                theater_centrality, prioritized_collection_targets,
            )

            _actors = getattr(getattr(session, "state_context", None), "actors", None)
            _p7_cc = str(
                getattr(_actors, "subject_country", None)
                or getattr(session, "learning_country", None)
                or "UNKNOWN"
            ).upper()
            session.p7_adjusted_forecast = adjusted_probability(_p7_cc)
            session.p7_risk_summary = global_risk_summary()
            session.p7_systemic_cascade = global_black_swan()
            from engine.Layer7_GlobalModel.global_state import GLOBAL_THEATERS as _p7_gt
            _p7_cent_codes = set(_p7_gt.keys()) | {_p7_cc, "USA", "RUS", "CHN"}
            session.p7_centrality = {cc: theater_centrality(cc) for cc in sorted(_p7_cent_codes)}
            session.p7_collection_priority = prioritized_collection_targets()

            _p7_spill = float(session.p7_adjusted_forecast.get("spillover", 0.0) or 0.0)
            if _p7_spill > 0.005:
                logger.info("[PHASE7] Cross-theater spillover: +%.1f%% to P(HIGH)", _p7_spill * 100)

            logger.info(
                "[PHASE7] Global risk: total_sre=%.3f, systemic=%s, active=%d theaters",
                session.p7_risk_summary.get("total_sre", 0),
                session.p7_systemic_cascade,
                session.p7_risk_summary.get("active_count", 0),
            )
        else:
            session.p7_adjusted_forecast = {}
            session.p7_risk_summary = {}
            session.p7_systemic_cascade = False
            session.p7_centrality = {}
            session.p7_collection_priority = []
    except Exception as _p7_fc_exc:
        logger.warning("[PHASE7] Cross-theater forecast failed: %s", _p7_fc_exc)
        session.p7_adjusted_forecast = {}
        session.p7_risk_summary = {}
        session.p7_systemic_cascade = False
        session.p7_centrality = {}
        session.p7_collection_priority = []

    # ── Sensor anchoring bias correction ──────────────────────────
    # Fix 7: The old rule penalised when confidence agreed with sensor,
    # which is backwards — agreement validated by good meta quality is
    # correct.  New rule: only penalise when agreement occurs AND meta
    # quality is low (suggesting circular/non-independent computation).
    _divergence = abs(weighted_confidence - float(sensor_score))
    if _divergence < 0.05 and meta_conf < 0.30:
        weighted_confidence *= 0.95
        weighted_confidence = max(0.0, min(1.0, weighted_confidence))
        logger.info(
            "[CONF-FIX7] SENSOR_ANCHORING: divergence=%.3f < 0.05 AND meta_conf=%.3f < 0.30 "
            "-> penalty x0.95 -> conf=%.3f",
            _divergence, meta_conf, weighted_confidence,
        )
    else:
        logger.info(
            "[CONF-FIX7] No anchoring bias: divergence=%.3f meta_conf=%.3f",
            _divergence, meta_conf,
        )

    # ── Gap & contradiction penalties ─────────────────────────────
    _gap_report = getattr(session, "gap_report", None)
    _gap_penalty = 0.0
    _contradiction_penalty = 0.0
    _gap_count = 0
    _contradiction_count = 0
    if _gap_report is not None:
        _gap_penalty = float(getattr(_gap_report, "gap_penalty", 0.0) or 0.0)
        _contradiction_penalty = float(getattr(_gap_report, "contradiction_penalty", 0.0) or 0.0)
        _gap_count = int(getattr(_gap_report, "gap_count", 0) or 0)
        _contradiction_count = int(getattr(_gap_report, "contradiction_count", 0) or 0)
    weighted_confidence -= _gap_penalty
    weighted_confidence -= _contradiction_penalty
    if _gap_penalty > 0 or _contradiction_penalty > 0:
        logger.info(
            "[CONF-GAP] gaps=%d (penalty=%.3f) contradictions=%d (penalty=%.3f) -> conf=%.3f",
            _gap_count, _gap_penalty, _contradiction_count, _contradiction_penalty,
            weighted_confidence,
        )

    # ── Corroboration boost ───────────────────────────────────────
    if _num_sources >= 3:
        _corr_boost = 0.05
        weighted_confidence += _corr_boost
        logger.info("[CONF-CORR] %d sources -> +%.2f corroboration boost", _num_sources, _corr_boost)

    # ── Council adjustment / shadow mode ──────────────────────────
    from Config.config import COUNCIL_SHADOW_MODE as _SHADOW
    _council_adj = float(getattr(session, "council_adjustment", 0.0) or 0.0)
    _gt_penalty = float(getattr(session, "groupthink_penalty", 0.0) or 0.0)
    _conf_before_council = weighted_confidence

    if _SHADOW:
        _hypothetical = weighted_confidence
        if _council_adj != 0.0:
            _hypothetical += _council_adj
        if _gt_penalty > 0:
            _hypothetical -= _gt_penalty
        _hypothetical = max(0.05, min(0.95, _hypothetical))
        logger.info(
            "[COUNCIL-SHADOW] adj=%+.4f gt_pen=%.4f | actual_conf=%.4f | hypothetical_conf=%.4f | delta=%+.4f",
            _council_adj, _gt_penalty, weighted_confidence, _hypothetical,
            _hypothetical - weighted_confidence,
        )
        session.shadow_conf_without_council = round(weighted_confidence, 6)
        session.shadow_conf_with_council = round(_hypothetical, 6)
        session.shadow_council_delta = round(_hypothetical - weighted_confidence, 6)
        session.shadow_mode_active = True
    else:
        if _council_adj != 0.0:
            weighted_confidence += _council_adj
            logger.info("[CONF-COUNCIL] adjustment=%+.4f -> conf=%.3f", _council_adj, weighted_confidence)
        if _gt_penalty > 0:
            weighted_confidence -= _gt_penalty
            logger.info("[CONF-COUNCIL] groupthink penalty=-%.4f -> conf=%.3f", _gt_penalty, weighted_confidence)
        session.shadow_conf_without_council = round(_conf_before_council, 6)
        session.shadow_conf_with_council = round(weighted_confidence, 6)
        session.shadow_council_delta = round(weighted_confidence - _conf_before_council, 6)
        session.shadow_mode_active = False

    weighted_confidence = max(0.05, min(0.95, weighted_confidence))

    # ── Uncertainty explanation ────────────────────────────────────
    _uncertainty_reason = ""
    if weighted_confidence < 0.50 and _gap_count >= 2:
        _gap_report_obj = getattr(session, "gap_report", None)
        if _gap_report_obj and getattr(_gap_report_obj, "uncertainty_explanation", ""):
            _uncertainty_reason = _gap_report_obj.uncertainty_explanation
        else:
            _uncertainty_reason = (
                f"Assessment unstable: {_gap_count} structural gaps and "
                f"{_contradiction_count} contradictions reduce analytic confidence."
            )
        logger.info("[UNCERTAINTY] %s", _uncertainty_reason)
    session.uncertainty_explanation = _uncertainty_reason

    return weighted_confidence
