"""
Withheld Re-collection — Gate-driven directed evidence loop
=============================================================
Extracted from coordinator.process_query WITHHELD → Directed Collection block.

When the Layer-5 gate withholds an assessment *and* provides PIRs,
this module executes up to ``MAX_CYCLES`` rounds of:

  1. Convert gate intelligence_gaps / PIRs → typed PIR dicts
  2. Directed collection (hypothesis → observable → search → belief)
  3. World Monitor cache fallback
  4. Re-deliberate council with updated state
  5. Re-evaluate gate

The loop breaks early when the gate approves or no new evidence is
found.  The caller receives the (possibly updated) ``gate_verdict``,
``session``, and ``analysis_result``.
"""
from __future__ import annotations

import logging
import re as _re
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)

MAX_CYCLES = 2


def run_recollection_loop(
    session: Any,
    coordinator: Any,
    gate_verdict: Any,
    gate_build_state: Callable,
    gate_evaluate: Callable,
) -> Tuple[Any, Any, Any]:
    """Execute the WITHHELD → directed-collection feedback loop.

    Parameters
    ----------
    session : CouncilSession
        Current deliberation session (mutated in-place on re-deliberation).
    coordinator : CouncilCoordinator
        Reference for ``convene_council``, ``_detect_conflicts``,
        ``_synthesize_decision``, ``_reset_for_reanalysis``, ``generate_result``.
    gate_verdict : GateVerdict
        Initial gate verdict (``withheld=True``).
    gate_build_state : callable
        ``gate_build_state(session) -> GateState``
    gate_evaluate : callable
        ``gate_evaluate(gate_state) -> GateVerdict``

    Returns
    -------
    tuple of (session, gate_verdict, analysis_result)
        Updated versions after 0–MAX_CYCLES re-collection rounds.
    """
    analysis_result = coordinator.generate_result(session)
    _total_new_beliefs = 0

    for _wh_cycle in range(MAX_CYCLES):
        if not gate_verdict.withheld:
            break  # Gate approved — exit loop
        if not gate_verdict.required_collection:
            break  # No PIRs to collect — nothing we can do

        logger.info(
            "[GATE→COLLECTION] WITHHELD cycle %d/%d — %d PIRs to fill",
            _wh_cycle + 1, MAX_CYCLES,
            len(gate_verdict.required_collection),
        )

        try:
            # 1. Convert gate intelligence_gaps + PIRs → typed PIR dicts
            pir_dicts = _build_pir_dicts(gate_verdict)
            if not pir_dicts:
                break

            # 2. Resolve country code
            country = _resolve_country(session)

            # 3. Directed collection (hypothesis-driven)
            _directed_evidence_found, n_beliefs = _run_directed_collection(
                pir_dicts, session, country,
            )
            _total_new_beliefs += n_beliefs

            # 4. World Monitor cache fallback
            if not _directed_evidence_found:
                _directed_evidence_found = _world_monitor_fallback(session, country)

            if not _directed_evidence_found:
                logger.info("[GATE→COLLECTION] No new evidence found — aborting re-collection")
                break

            # 5. Re-deliberate with updated state
            coordinator._reset_for_reanalysis(session)
            session = coordinator.convene_council(session)
            session = coordinator._detect_conflicts(session)
            session = coordinator._synthesize_decision(
                session,
                verification_score=float(session.verification_score),
            )

            # 6. Regenerate result and re-evaluate gate
            analysis_result = coordinator.generate_result(session)

            try:
                gate_state = gate_build_state(session)
                gate_state.directed_beliefs_added = _total_new_beliefs
                gate_state.withheld_cycle = _wh_cycle + 1
                gate_verdict = gate_evaluate(gate_state)
            except Exception as _ge:
                logger.error("[GATE] Re-evaluation failed: %s", _ge)
                break

            logger.info(
                "[GATE→COLLECTION] After cycle %d: verdict=%s (new_beliefs=%d)",
                _wh_cycle + 1, gate_verdict.decision, _total_new_beliefs,
            )

        except ImportError as _ie:
            logger.warning("[GATE→COLLECTION] Collection bridge unavailable: %s", _ie)
            break
        except Exception as _ce:
            logger.warning("[GATE→COLLECTION] Re-collection failed: %s", _ce)
            break

    return session, gate_verdict, analysis_result


# ── internal helpers ──────────────────────────────────────────────────

def _build_pir_dicts(gate_verdict: Any) -> List[dict]:
    """Convert gate intelligence_gaps + PIR text + collection_tasks → typed dicts."""
    pir_dicts: List[dict] = []

    # Primary: use intelligence_gaps (raw signal tokens)
    for sig in (gate_verdict.intelligence_gaps or []):
        sig = str(sig).strip().upper()
        if sig.startswith("SIG_") and sig not in [p["signal"] for p in pir_dicts]:
            pir_dicts.append({
                "signal": sig,
                "modality": "OSINT",
                "priority": "HIGH",
                "reason": f"Gate WITHHELD — missing {sig}",
            })

    # Secondary: extract signals from PIR text descriptions
    for pir_text in (gate_verdict.required_collection or []):
        sig_match = _re.search(r"(SIG_[A-Z_]+)", str(pir_text))
        if sig_match:
            sig = sig_match.group(1)
            if sig not in [p["signal"] for p in pir_dicts]:
                pir_dicts.append({
                    "signal": sig,
                    "modality": "OSINT",
                    "priority": "HIGH",
                    "reason": str(pir_text),
                })

    # Also include collection_tasks from gate verdict
    for ct in (gate_verdict.collection_tasks or []):
        ct_sig = str(ct.get("signal", "")).strip().upper()
        if ct_sig and ct_sig not in [p["signal"] for p in pir_dicts]:
            pir_dicts.append({
                "signal": ct_sig,
                "modality": str(ct.get("modality", "OSINT")),
                "priority": str(ct.get("priority", "HIGH")),
                "reason": str(ct.get("reason", "")),
            })

    return pir_dicts


def _resolve_country(session: Any) -> str:
    """Best-effort country code from session state."""
    country = str(
        getattr(getattr(session.state_context, "actors", None), "subject_country", "")
        or ""
    )
    if not country or country.upper() == "UNKNOWN":
        country = str(
            getattr(session.state_context, "country_code", "")
            or getattr(session, "country_code", "")
            or ""
        )
    return country


def _run_directed_collection(
    pir_dicts: List[dict],
    session: Any,
    country: str,
) -> Tuple[bool, int]:
    """Execute directed collection and return (found_evidence, n_beliefs)."""
    try:
        from Core.intelligence.collection_bridge import execute_directed_collection

        dc_result = execute_directed_collection(
            pir_dicts=pir_dicts,
            state_context=session.state_context,
            country=country,
            max_observables_per_signal=5,
            max_total_docs=20,
        )

        n_obs = len(dc_result.get("observations", []))
        n_beliefs = len(dc_result.get("beliefs", []))
        n_updated = len(dc_result.get("signals_updated", []))
        n_docs = dc_result.get("documents_collected", 0)

        found = n_beliefs > 0 or n_updated > 0

        logger.info(
            "[GATE→COLLECTION] Directed collection: %d docs → %d obs → %d beliefs → %d signals updated",
            n_docs, n_obs, n_beliefs, n_updated,
        )

        searched = dc_result.get("signals_searched", [])
        if searched:
            logger.info(
                "[GATE→COLLECTION] Hypothesis expansion searched: %s",
                ", ".join(searched),
            )

        return found, n_beliefs

    except ImportError as _dc_ie:
        logger.debug("[GATE→COLLECTION] Directed collection unavailable: %s", _dc_ie)
        return False, 0
    except Exception as _dc_err:
        logger.warning("[GATE→COLLECTION] Directed collection error: %s", _dc_err)
        return False, 0


def _world_monitor_fallback(session: Any, country: str) -> bool:
    """Inject cached World Monitor state when directed collection produced nothing."""
    try:
        from runtime.world_monitor import get_prebuilt_state, is_state_fresh

        if country and is_state_fresh(country, max_age_minutes=120):
            cached = get_prebuilt_state(country)
            if cached and cached.get("signal_confidence"):
                _wm_hits = []
                for sig_name, conf in cached["signal_confidence"].items():
                    if float(conf) > 0.10:
                        _wm_hits.append((sig_name, float(conf)))
                if _wm_hits and hasattr(session.state_context, "signal_confidence"):
                    for sig_name, conf in _wm_hits:
                        existing = float(
                            session.state_context.signal_confidence.get(sig_name, 0.0) or 0.0
                        )
                        merged = max(existing, conf * 0.50)
                        session.state_context.signal_confidence[sig_name] = merged
                    logger.info(
                        "[GATE→COLLECTION] World Monitor cache injected %d signals for %s",
                        len(_wm_hits), country,
                    )
                    return True
    except ImportError:
        pass
    except Exception as _wm_err:
        logger.debug("[GATE→COLLECTION] World Monitor fallback error: %s", _wm_err)

    return False
