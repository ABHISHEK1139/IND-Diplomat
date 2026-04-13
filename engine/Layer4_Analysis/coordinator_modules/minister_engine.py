"""
Minister Engine — Minister orchestration with default hypothesis fallback.

Adds a **fallback layer** so ministers never return empty predicted_signals.
Does NOT modify any minister source code.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer4_Analysis.coordinator_modules.minister_engine")

# ── Default hypotheses per minister ──────────────────────────────
# Applied when a minister's LLM reasoning returns empty predictions.
# This ensures every dimension always has testable hypotheses.

DEFAULT_HYPOTHESES: Dict[str, List[str]] = {
    "Security Minister": [
        "SIG_MIL_MOBILIZATION",
        "SIG_FORCE_POSTURE",
        "SIG_LOGISTICS_PREP",
        "SIG_MIL_ESCALATION",
        "SIG_CYBER_ACTIVITY",
    ],
    "Economic Minister": [
        "SIG_ECONOMIC_PRESSURE",
        "SIG_ALLIANCE_ACTIVATION",
    ],
    "Domestic Minister": [
        "SIG_INTERNAL_INSTABILITY",
        "SIG_PUBLIC_PROTEST",
        "SIG_DECEPTION_ACTIVITY",
    ],
    "Diplomatic Minister": [
        "SIG_DIPLOMACY_ACTIVE",
        "SIG_NEGOTIATION_BREAKDOWN",
        "SIG_COERCIVE_BARGAINING",
        "SIG_DETERRENCE_SIGNALING",
        "SIG_DIP_HOSTILITY",
    ],
    "Strategy Minister": [
        "SIG_FORCE_POSTURE",
        "SIG_MIL_ESCALATION",
        "SIG_COERCIVE_BARGAINING",
    ],
    "Alliance Minister": [
        "SIG_ALLIANCE_ACTIVATION",
        "SIG_DIPLOMACY_ACTIVE",
    ],
    "Contrarian Minister": [
        "SIG_DIPLOMACY_ACTIVE",
        "SIG_ALLIANCE_ACTIVATION",
    ],
}


def convene_ministers(
    session: Any,
    *,
    apply_defaults: bool = True,
) -> Any:
    """
    Run the council of ministers and apply default hypothesis fallback.

    1. Delegates to ``CouncilCoordinator.convene_council()``
    2. If any minister returned empty ``predicted_signals``,
       injects ``DEFAULT_HYPOTHESES`` for that role.

    This is a **post-processing layer** — the core coordinator
    is called unchanged.

    Parameters
    ----------
    session : CouncilSession
        The session to convene.
    apply_defaults : bool
        If True, fill empty hypotheses with defaults.

    Returns
    -------
    CouncilSession
        Updated session with hypotheses guaranteed non-empty.
    """
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator

    coord = CouncilCoordinator()
    session = coord.convene_council(session)

    if apply_defaults:
        _apply_hypothesis_defaults(session)

    return session


def _apply_hypothesis_defaults(session: Any) -> None:
    """
    Fill empty predicted_signals with default hypotheses.

    Only runs on minister reports that returned [] for predicted_signals.
    Does NOT overwrite existing predictions.
    """
    if not hasattr(session, "ministers_reports"):
        return

    for report in session.ministers_reports.values():
        minister_name = getattr(report, "minister_name", "")
        predicted = getattr(report, "predicted_signals", None)

        if predicted is None or len(predicted) == 0:
            defaults = DEFAULT_HYPOTHESES.get(minister_name, [])
            if defaults:
                report.predicted_signals = list(defaults)
                logger.info(
                    "[MINISTER-FALLBACK] %s had empty predictions → injected %d defaults: %s",
                    minister_name, len(defaults), defaults,
                )
