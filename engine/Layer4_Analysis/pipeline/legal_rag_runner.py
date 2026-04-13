"""
Legal RAG Runner — Post-gate 4-brain legal evidence engine
============================================================
Extracted from coordinator.process_query post-gate legal RAG block.

Brain 1 — Retriever: find candidate text (rag_bridge)
Brain 2 — Filter: signal legal mapper + treaty validator
Brain 2a — Signal interpreter → behavior-based RAG augmentation
Brain 3 — Analyst: LLM legal applicability analysis
Brain 4 — Reasoner: hallucination validation

Entire module is gated behind ``ENABLE_LEGAL_MODULE``.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


def run_post_gate_legal_rag(
    session: Any,
    question: str,
    country: str,
) -> Tuple[List[dict], float, Dict[str, Any], List[dict], List[Any]]:
    """Execute the full post-gate legal evidence pipeline.

    Returns
    -------
    tuple of (rag_evidence, doc_conf, constraint_analysis, evidence_items_dicts, inferred_behaviors)
        Results are also persisted on ``session`` attributes.
    """
    from Config.config import ENABLE_LEGAL_MODULE as _LEGAL_ON

    _post_gate_rag: list = []
    _post_gate_doc_conf = 0.0
    _legal_constraint_analysis: dict = {}
    _legal_evidence_items: list = []
    _inferred_behaviors: list = []

    if not _LEGAL_ON:
        logger.info("[LEGAL] Module disabled — skipping post-gate RAG, LLM reasoner, treaty validator")
        _persist(session, _post_gate_rag, _post_gate_doc_conf, _legal_constraint_analysis, _legal_evidence_items, _inferred_behaviors)
        return _post_gate_rag, _post_gate_doc_conf, _legal_constraint_analysis, _legal_evidence_items, _inferred_behaviors

    # ── Brain 1 + 2: Retrieve + Filter ────────────────────────────
    try:
        from Core.legal.rag_bridge import retrieve_legal_evidence
        from engine.Layer3_StateModel.evidence_support import compute_document_confidence

        _observed: Set[str] = set(getattr(session.state_context, "observed_signals", set()) or set())
        _target = str(
            getattr(getattr(session.state_context, "actors", None), "target_country", "") or ""
        )

        # Brain 2a: Signal Legal Mapper
        _legal_signals = _observed  # fallback: use all signals
        try:
            from Core.legal.signal_legal_mapper import filter_legal_signals
            _filtered = filter_legal_signals(_observed)
            if _filtered:
                _legal_signals = _filtered
                logger.info(
                    "[POST-GATE RAG] Legal mapper: %d/%d signals require legal analysis",
                    len(_legal_signals), len(_observed),
                )
        except Exception as _map_err:
            logger.debug("[POST-GATE RAG] Signal mapper unavailable: %s", _map_err)

        # ── Signal Interpreter: translate signals → concrete behaviors ──
        _behaviors_block = ""
        try:
            from Core.legal.signal_interpreter import interpret_signals, behaviors_to_prompt_block

            _escalation = float(
                getattr(session, "sre_score", 0.0) or
                getattr(getattr(session, "state_context", None), "escalation_score", 0.0) or 0.0
            )

            _inferred_behaviors = interpret_signals(
                _legal_signals,
                subject_country=country,
                target_country=_target,
                escalation_score=_escalation,
            )
            if _inferred_behaviors:
                _behaviors_block = behaviors_to_prompt_block(_inferred_behaviors)
                logger.info(
                    "[POST-GATE INTERPRETER] %d behavior(s) inferred from %d signal(s)",
                    len(_inferred_behaviors), len(_legal_signals),
                )
        except Exception as _interp_err:
            logger.debug("[POST-GATE INTERPRETER] Signal interpreter unavailable: %s", _interp_err)

        _rag_raw = retrieve_legal_evidence(
            _legal_signals, n_results=5, country_code=country,
            target_country=_target,
        )

        # ── Behavior-based RAG augmentation ───────────────────────
        if _inferred_behaviors:
            try:
                from Core.legal.signal_interpreter import behaviors_to_rag_queries
                from Core.legal.rag_bridge import _try_import_indexer

                _beh_queries = behaviors_to_rag_queries(_inferred_behaviors)[:8]
                _query_fn = _try_import_indexer()
                if _query_fn and _beh_queries:
                    for _bq in _beh_queries:
                        try:
                            _bq_raw = _query_fn(query=_bq, n_results=2)
                            _bq_docs = (_bq_raw.get("documents") or [[]])[0]
                            _bq_metas = (_bq_raw.get("metadatas") or [[]])[0]
                            _bq_dists = (_bq_raw.get("distances") or [[]])[0]
                            for _dt, _dm, _dd in zip(_bq_docs, _bq_metas, _bq_dists):
                                if _dt and (1.0 - _dd / 2.0) >= 0.30:
                                    _rag_raw.append({
                                        "signal": "BEHAVIOR_QUERY",
                                        "query": _bq[:200],
                                        "article_text": _dt[:2000],
                                        "source": _dm.get("source", "unknown"),
                                        "root": _dm.get("root", "unknown"),
                                        "distance": round(_dd, 4),
                                        "relevance": round(1.0 - _dd / 2.0, 4),
                                        "treaty_name": _dm.get("treaty_name", ""),
                                        "article_number": _dm.get("article_number", ""),
                                        "domain": _dm.get("domain", ""),
                                        "year": _dm.get("year", ""),
                                        "heading": _dm.get("heading", ""),
                                        "country": _dm.get("country", ""),
                                        "chunk_type": _dm.get("chunk_type", ""),
                                    })
                        except Exception:
                            pass
                    logger.info(
                        "[POST-GATE RAG] Behavior-augmented: %d total articles after %d behavior queries",
                        len(_rag_raw), len(_beh_queries),
                    )
            except Exception as _beh_rag_err:
                logger.debug("[POST-GATE RAG] Behavior query augmentation failed: %s", _beh_rag_err)

        if _rag_raw:
            _seen_rag: set = set()
            for _doc in _rag_raw:
                _dk = (
                    str(_doc.get("treaty_name", "")),
                    str(_doc.get("article_number", "")),
                    str(_doc.get("excerpt", _doc.get("article_text", "")))[:200],
                )
                if _dk not in _seen_rag:
                    _seen_rag.add(_dk)
                    _post_gate_rag.append(_doc)

            _proj_sigs = list(
                getattr(session.state_context, "projected_signals", {}) or {}
            )
            _post_gate_doc_conf = compute_document_confidence(
                _proj_sigs, _post_gate_rag,
            )

            logger.info(
                "[POST-GATE RAG] %d legal article(s) retrieved, doc_conf=%.3f",
                len(_post_gate_rag), _post_gate_doc_conf,
            )
    except Exception as _rag_err:
        logger.warning("[POST-GATE RAG] Retrieval failed: %s — proceeding without", _rag_err)

    # ── Brain 3+4: Legal Evidence Engine (LLM reasoning + validation) ──
    try:
        from Core.legal.legal_evidence_formatter import format_legal_evidence
        from Core.legal.legal_reasoner import LegalReasoner
        from Core.legal.legal_output_validator import validate_legal_output

        _evidence_items = format_legal_evidence(_post_gate_rag)
        _legal_evidence_items = [item.to_dict() for item in _evidence_items]

        if _evidence_items:
            _reasoner = LegalReasoner()
            _llm_result = _reasoner.analyze_legal_constraints(
                evidence_items=_evidence_items,
                subject_country=country,
                target_country=_target if '_target' in dir() else "",
                active_signals=_legal_signals if '_legal_signals' in dir() else set(),
                behaviors_block=_behaviors_block if '_behaviors_block' in dir() else "",
            )

            _raw_constraints = _llm_result.get("legal_constraints", [])
            if _raw_constraints:
                _validation = validate_legal_output(
                    llm_constraints=_raw_constraints,
                    evidence_items=_evidence_items,
                )
                _legal_constraint_analysis = {
                    "validated_constraints": _validation["validated_constraints"],
                    "dropped_constraints": _validation["dropped_constraints"],
                    "hallucinations_blocked": _validation["hallucinations_blocked"],
                    "total_evaluated": _validation["total_evaluated"],
                    "llm_used": _llm_result.get("llm_used", False),
                    "error": _llm_result.get("error"),
                }
            else:
                _legal_constraint_analysis = {
                    "validated_constraints": [],
                    "dropped_constraints": [],
                    "hallucinations_blocked": 0,
                    "total_evaluated": 0,
                    "llm_used": _llm_result.get("llm_used", False),
                    "error": _llm_result.get("error"),
                }

            logger.info(
                "[LEGAL-ENGINE] %d constraints, %d validated, %d hallucinations blocked",
                len(_raw_constraints),
                len(_legal_constraint_analysis.get("validated_constraints", [])),
                _legal_constraint_analysis.get("hallucinations_blocked", 0),
            )
    except Exception as _legal_err:
        logger.warning("[LEGAL-ENGINE] Legal reasoning failed: %s — proceeding without", _legal_err)

    _persist(session, _post_gate_rag, _post_gate_doc_conf, _legal_constraint_analysis, _legal_evidence_items, _inferred_behaviors)
    return _post_gate_rag, _post_gate_doc_conf, _legal_constraint_analysis, _legal_evidence_items, _inferred_behaviors


def _persist(
    session: Any,
    rag: list,
    doc_conf: float,
    constraints: dict,
    evidence_items: list,
    behaviors: list,
) -> None:
    """Persist legal results on session for downstream serialisation."""
    session.rag_evidence = rag
    session.document_confidence = doc_conf
    session.legal_constraint_analysis = constraints
    session.legal_evidence_items = evidence_items
    session.inferred_behaviors = (
        [b.to_dict() for b in behaviors]
        if behaviors and hasattr(behaviors[0], "to_dict")
        else []
    )
