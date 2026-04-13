"""
Core.legal.legal_reasoner — Deterministic + LLM Legal Reasoning
=================================================================

Two modes:

1. **Deterministic** (``evaluate()``) — pre-gate signal→signal mapping.
   Converts observed empirical signals into legal-domain escalation
   signals.  No LLM.  Always available.

2. **LLM Applicability Analysis** (``analyze_legal_constraints()``) —
   post-gate only.  Takes structured evidence items from the formatter,
   sends them to Ollama/deepseek-r1:8b with the constrained legal
   reasoner prompt, and returns a structured JSON dict of legal
   constraints (prohibited/permitted/conditional/restricted/unclear).

   Graceful fallback: if LLM is unavailable, returns an empty result
   rather than crashing the pipeline.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Set

logger = logging.getLogger("Core.legal.legal_reasoner")


def _norm(signal: str) -> str:
    return str(signal or "").strip().upper()


class LegalReasoner:
    """
    Dual-mode legal reasoning engine.

    - ``evaluate()`` — deterministic signal mapping (pre-gate)
    - ``analyze_legal_constraints()`` — LLM applicability analysis (post-gate)
    """

    RULES: Dict[str, Set[str]] = {
        # Sovereignty / use of force
        "SIG_SOVEREIGNTY_BREACH": {
            "SIG_MIL_ESCALATION",
            "SIG_BORDER_CLASH",
            "SIG_MIL_BORDER_CLASHES",
            "SIG_TERRITORIAL_INCURSION",
            "SIG_FORCE_CONCENTRATION",
        },
        # Maritime freedom / UNCLOS pressure
        "SIG_MARITIME_VIOLATION": {
            "SIG_CHOKEPOINT_CONTROL",
            "SIG_BLOCKADE",
            "SIG_FORCE_POSTURE",
            "SIG_LOGISTICS_SURGE",
            "SIG_MIL_FORWARD_DEPLOYMENT",
        },
        # Economic coercion
        "SIG_ILLEGAL_COERCION": {
            "SIG_SANCTIONS_ACTIVE",
            "SIG_ECO_SANCTIONS_ACTIVE",
            "SIG_ECONOMIC_PRESSURE",
        },
        # Treaty/negotiation obligations
        "SIG_TREATY_VIOLATION": {
            "SIG_TREATY_BREAK",
            "SIG_DIP_BREAK",
            "SIG_NEGOTIATION_BREAKDOWN",
            "SIG_DIP_CHANNEL_CLOSURE",
        },
        # Cyber sovereignty
        "SIG_CYBER_SOVEREIGNTY_VIOLATION": {
            "SIG_CYBER_ACTIVITY",
            "SIG_CYBER_PREPARATION",
            "SIG_CAP_CYBER_PREPARATION",
        },
    }

    # ── Mode 1: Deterministic (unchanged) ────────────────────────

    def evaluate(self, observed_signals: Iterable[str]) -> Set[str]:
        observed = {_norm(token) for token in list(observed_signals or []) if _norm(token)}
        legal_signals: Set[str] = set()
        for legal_signal, triggers in self.RULES.items():
            if observed & set(triggers):
                legal_signals.add(legal_signal)
        return legal_signals

    def supporting_observed_signals(self, legal_signal: str, observed_signals: Iterable[str]) -> List[str]:
        token = _norm(legal_signal)
        triggers = set(self.RULES.get(token, set()))
        observed = {_norm(item) for item in list(observed_signals or []) if _norm(item)}
        return sorted(list(observed & triggers))

    # ── Mode 2: LLM Applicability Analysis (post-gate) ──────────

    def analyze_legal_constraints(
        self,
        evidence_items: List[Any],
        subject_country: str = "",
        target_country: str = "",
        active_signals: Optional[Set[str]] = None,
        behaviors_block: str = "",
    ) -> Dict[str, Any]:
        """
        Use the LLM to perform legal applicability analysis.

        Parameters
        ----------
        evidence_items : list[LegalEvidenceItem]
            Structured evidence from ``legal_evidence_formatter``.
        subject_country : str
            ISO code of the subject actor.
        target_country : str
            ISO code of the target actor.
        active_signals : set[str], optional
            Signal codes that triggered legal retrieval.
        behaviors_block : str, optional
            Pre-formatted inferred behaviors from signal_interpreter.

        Returns
        -------
        dict
            ``{"legal_constraints": [...], "llm_used": True/False,
              "error": None or str}``
        """
        if not evidence_items:
            logger.info("[LEGAL-REASONER] No evidence items — skipping LLM analysis")
            return {"legal_constraints": [], "llm_used": False, "error": None}

        # Cap evidence to top N by confidence to stay within LLM context limits
        MAX_EVIDENCE_FOR_LLM = 15
        if len(evidence_items) > MAX_EVIDENCE_FOR_LLM:
            _sorted = sorted(evidence_items, key=lambda e: e.confidence, reverse=True)
            evidence_items = _sorted[:MAX_EVIDENCE_FOR_LLM]
            logger.info(
                "[LEGAL-REASONER] Capped evidence from %d to %d (top by confidence)",
                len(_sorted), MAX_EVIDENCE_FOR_LLM,
            )

        # Build prompt
        try:
            from Core.legal.legal_evidence_formatter import evidence_to_prompt_block
            from Core.legal.legal_reasoner_prompt import SYSTEM_PROMPT, build_user_prompt

            evidence_block = evidence_to_prompt_block(evidence_items)
            user_prompt = build_user_prompt(
                subject_country=subject_country,
                target_country=target_country,
                active_signals=active_signals or set(),
                evidence_block=evidence_block,
                behaviors_block=behaviors_block,
            )
        except Exception as e:
            logger.warning("[LEGAL-REASONER] Prompt assembly failed: %s", e)
            return {"legal_constraints": [], "llm_used": False, "error": str(e)}

        # Call LLM
        try:
            from engine.Layer4_Analysis.core.llm_client import LocalLLM

            llm = LocalLLM()
            legal_max_tokens_raw = str(os.getenv("LEGAL_REASONER_MAX_TOKENS", "")).strip()
            legal_max_tokens = int(legal_max_tokens_raw) if legal_max_tokens_raw else None
            raw_response = llm.generate(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.1,
                json_mode=True,
                max_tokens=legal_max_tokens,
                timeout=600,
            )

            if raw_response.startswith("LLM_ERROR:"):
                logger.warning("[LEGAL-REASONER] LLM call failed: %s", raw_response)
                return {"legal_constraints": [], "llm_used": False, "error": raw_response}

            # Parse JSON response
            parsed = self._parse_llm_response(raw_response)
            if parsed is None:
                logger.warning("[LEGAL-REASONER] Could not parse LLM JSON response")
                return {
                    "legal_constraints": [],
                    "llm_used": True,
                    "error": "JSON parse failure",
                    "raw_response": raw_response[:500],
                }

            constraints = parsed.get("legal_constraints", [])
            if not isinstance(constraints, list):
                constraints = []

            logger.info(
                "[LEGAL-REASONER] LLM returned %d legal constraint(s)",
                len(constraints),
            )

            return {
                "legal_constraints": constraints,
                "llm_used": True,
                "error": None,
            }

        except ImportError:
            logger.warning("[LEGAL-REASONER] LLM client not available — skipping")
            return {"legal_constraints": [], "llm_used": False, "error": "llm_client_unavailable"}
        except Exception as e:
            logger.warning("[LEGAL-REASONER] LLM analysis failed: %s", e)
            return {"legal_constraints": [], "llm_used": False, "error": str(e)}

    @staticmethod
    def _parse_llm_response(raw: str) -> Optional[Dict[str, Any]]:
        """
        Robust JSON extraction from LLM output.
        Handles deepseek-r1 <think> blocks, markdown fences, and noise.
        """
        text = str(raw or "").strip()
        if not text:
            return None

        # 1. Strip <think>...</think> reasoning blocks
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # 2. Extract from code fences
        fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()

        # 3. Direct parse
        try:
            return json.loads(text)
        except Exception:
            pass

        # 4. Find outermost { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start: end + 1])
            except Exception:
                pass

        return None
