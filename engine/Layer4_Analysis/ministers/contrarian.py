"""
ContrarianMinister — Phase 8 Devil's Advocate
===============================================

Argues AGAINST the emerging consensus.  When ministers converge on
escalation, the Contrarian highlights de-escalation signals and
stabilising factors.  When ministers converge on LOW, the Contrarian
highlights latent risks and warning indicators.

This is NOT the Red Team (which challenges after the council decides).
The Contrarian participates IN the council debate so its arguments are
weighed alongside the other ministers before a decision is reached.

Dimension: CONTRARIAN (cross-cutting — not tied to a single SRE domain).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.council_session import MinisterReport
from engine.Layer4_Analysis.ministers.base import BaseMinister, _pick, _as_float

logger = logging.getLogger(__name__)

# Signals that indicate potential de-escalation / stability
_DE_ESCALATION_SIGNALS: List[str] = [
    "SIG_DIPLOMACY_ACTIVE",
    "SIG_ALLIANCE_ACTIVATION",
]

# Signals that indicate latent escalation risk
_LATENT_RISK_SIGNALS: List[str] = [
    "SIG_MIL_ESCALATION",
    "SIG_LOGISTICS_PREP",
    "SIG_CYBER_ACTIVITY",
    "SIG_COERCIVE_PRESSURE",
    "SIG_FORCE_POSTURE",
    "SIG_MIL_MOBILIZATION",
    "SIG_DECEPTION_ACTIVITY",
]


class ContrarianMinister(BaseMinister):
    """Devil's advocate — argues the opposite case to break groupthink."""

    def __init__(self):
        super().__init__("Contrarian Minister")

    def _dimension(self) -> str:
        return "CONTRARIAN"

    def _pressure_classify(self, ctx: StateContext) -> Optional[MinisterReport]:
        """
        Pressure-based contrarian assessment.

        - If overall signal confidence is HIGH → highlight de-escalation factors.
        - If overall signal confidence is LOW → highlight latent risks.
        """
        sig_conf = getattr(ctx, "signal_confidence", {}) or {}
        proj = getattr(ctx, "projected_signals", {}) or {}

        # Determine consensus direction from average signal confidence
        active_confs = [
            float(v) for v in sig_conf.values() if float(v) > 0.0
        ] if sig_conf else []
        avg_conf = sum(active_confs) / len(active_confs) if active_confs else 0.0

        predicted: List[str] = []
        confidence = 0.0

        if avg_conf > 0.40:
            # Consensus is escalation → contrarian highlights de-escalation
            for sig_name in _DE_ESCALATION_SIGNALS:
                sig_obj = proj.get(sig_name)
                if sig_obj:
                    sc = float(getattr(sig_obj, "confidence", 0.0))
                    if sc > 0.1:
                        predicted.append(sig_name)

            # Also check for MISSING escalation signals that should
            # be present if a real escalation were underway
            for sig_name in _LATENT_RISK_SIGNALS:
                if sig_name not in proj:
                    # Signal absent — contrarian notes this as counter-evidence
                    pass

            confidence = max(0.20, 1.0 - avg_conf)
            logger.info(
                "[CONTRARIAN] Consensus HIGH (avg=%.2f) — arguing "
                "de-escalation. Highlighting %d stabilising signals.",
                avg_conf, len(predicted),
            )
        else:
            # Consensus is LOW → contrarian highlights latent risks
            for sig_name in _LATENT_RISK_SIGNALS:
                sig_obj = proj.get(sig_name)
                if sig_obj:
                    sc = float(getattr(sig_obj, "confidence", 0.0))
                    if sc > 0.05:  # even weak signals are highlighted
                        predicted.append(sig_name)

            confidence = min(0.80, avg_conf + 0.30)
            logger.info(
                "[CONTRARIAN] Consensus LOW (avg=%.2f) — arguing "
                "latent risk. Highlighting %d risk signals.",
                avg_conf, len(predicted),
            )

        if not predicted:
            return None

        return self._create_report(predicted, confidence)

    def deliberate(self, ctx: StateContext | Dict[str, Any]) -> Optional[MinisterReport]:
        ctx = self._coerce_state_context(ctx)
        if ctx is None:
            return None

        # Try pressure-based classification first (fast, no LLM)
        pressure_result = self._pressure_classify(ctx)
        if pressure_result:
            return pressure_result

        # Fallback to LLM-based contrarian analysis
        return self._ask_llm(
            state_context=ctx,
            specific_instructions=(
                "You are the CONTRARIAN minister. Your job is to argue the "
                "OPPOSITE of what the evidence seems to show. If signals suggest "
                "escalation, find de-escalation indicators. If signals suggest "
                "stability, find hidden risk factors. Identify signals that "
                "CONTRADICT the prevailing assessment. This prevents groupthink."
            ),
        )
