"""
The Council of Ministers — Base infrastructure.
Shared helpers, constants, and the abstract BaseMinister class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.council_session import MinisterReport
from engine.Layer4_Analysis.schema import Hypothesis
from engine.Layer4_Analysis.core.llm_client import LocalLLM, note_llm_deterministic_fallback
from engine.Layer4_Analysis.core.context_curator import (
    build_minister_classification_pack,
    build_minister_reasoning_pack,
    estimate_tokens,
)
from engine.Layer4_Analysis.core.critique_engine import (
    build_improvement_feedback,
    critique_minister_output,
)
from engine.Layer4_Analysis.core.intelligence_controller import (
    decide_effort,
    recommend_stage_output_budget,
    stage_budget_instruction,
)
from engine.Layer4_Analysis.core.reasoning_monitor import (
    analyze_output,
    build_adjustment_feedback,
    recommend_adjusted_budget,
)
from engine.layer4_reasoning.signal_ontology import SIGNAL_ONTOLOGY

logger = logging.getLogger(__name__)

# ── Role-specific focus areas used in reasoning prompts ───────────────
ROLE_FOCUS = {
    "Security Minister": (
        "CAPABILITY",
        "Focus on: kinetic activity, force posture, logistics preparation, "
        "cyber operations, military mobilization, escalation momentum. "
        "You may reference economics or diplomacy only if they directly "
        "affect military capability or operational readiness.",
    ),
    "Economic Minister": (
        "COST",
        "Focus on: sanctions impact, economic pressure, cost constraints, "
        "retaliatory economic leverage, trade disruption, supply chain "
        "vulnerability, financial system stress. You may reference "
        "military or diplomatic factors only if they create economic cost.",
    ),
    "Diplomatic Minister": (
        "INTENT",
        "Focus on: alliance activation, negotiation breakdown, coercive "
        "rhetoric, treaty signaling, diplomatic hostility, deterrence "
        "messaging. You may reference military posture only if it signals "
        "diplomatic intent.",
    ),
    "Domestic Minister": (
        "STABILITY",
        "Focus on: internal instability, regime stability, public protest, "
        "distraction theory dynamics, domestic political pressure, "
        "information operations. You may reference external dimensions "
        "only if they destabilise internal cohesion.",
    ),
    "Contrarian Minister": (
        "CONTRARIAN",
        "You are the devil's advocate. Argue AGAINST the emerging consensus. "
        "If other signals indicate escalation, highlight de-escalation factors "
        "and stabilising influences. If signals indicate stability, highlight "
        "hidden risks and latent escalation indicators. Your role is to "
        "prevent groupthink by surfacing the strongest counter-argument.",
    ),
}


ALLOWED_SIGNALS: List[str] = [
    "SIG_MIL_ESCALATION",
    "SIG_CYBER_ACTIVITY",
    "SIG_DIP_HOSTILITY",
    "SIG_ALLIANCE_SHIFT",
    "SIG_ECON_PRESSURE",
    "SIG_ECONOMIC_PRESSURE",
    "SIG_SANCTIONS_ACTIVE",
    "SIG_FORCE_POSTURE",
    "SIG_LOGISTICS_PREP",
    "SIG_DECEPTION_ACTIVITY",
    "SIG_NEGOTIATION_BREAKDOWN",
    "SIG_INTERNAL_INSTABILITY",
    # INTENT vocabulary (crisis-escalation phase detection)
    "SIG_ALLIANCE_ACTIVATION",
    "SIG_COERCIVE_PRESSURE",
    "SIG_COERCIVE_BARGAINING",
    "SIG_RETALIATORY_THREAT",
    "SIG_DETERRENCE_SIGNALING",
    # Extended COST / STABILITY
    "SIG_ECO_SANCTIONS_ACTIVE",
    "SIG_ECO_PRESSURE_HIGH",
    "SIG_MIL_MOBILIZATION",
    "SIG_DOM_INTERNAL_INSTABILITY",
    # Cooperative / de-escalation (GDELT sensor)
    "SIG_DIPLOMACY_ACTIVE",
    # Kinetic activity composite (confirmed strikes, casualties)
    "SIG_KINETIC_ACTIVITY",
]
_ALLOWED_SIGNAL_SET = set(ALLOWED_SIGNALS)


def _pick(root: Any, path: str, default: Any = 0.0) -> Any:
    current = root
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            current = getattr(current, key, default)
        if current is default:
            return default
    return current


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"high", "active", "true", "yes"}:
            return 1.0
        if token in {"medium", "moderate"}:
            return 0.6
        if token in {"low", "inactive", "none", "false", "no"}:
            return 0.0
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return max(0.0, min(1.0, float(default)))


def _as_signal_token(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def _is_high_token(value: Any) -> bool:
    return str(value or "").strip().lower() in {"high", "active", "true", "yes", "1"}


class BaseMinister(ABC):
    MAX_PREDICTED_SIGNALS = len(ALLOWED_SIGNALS)

    def __init__(self, name: str):
        self.name = name
        self.llm = LocalLLM()
        self.allowed_signals = list(ALLOWED_SIGNALS)

    def _dimension(self) -> str:
        return "UNKNOWN"

    @abstractmethod
    def deliberate(self, ctx: StateContext | Dict[str, Any]) -> Optional[MinisterReport]:
        """Classify state into allowed signal tokens."""
        pass

    @staticmethod
    def _coerce_state_context(ctx: StateContext | Dict[str, Any]) -> Optional[StateContext]:
        if isinstance(ctx, StateContext):
            return ctx
        if isinstance(ctx, dict):
            try:
                return StateContext.from_dict(ctx)
            except Exception:
                return None
        return None

    def produce_hypothesis(self, state_context: StateContext) -> Optional[Hypothesis]:
        """
        Produce a structured Hypothesis object from a minister report.
        """
        report = self.deliberate(state_context)
        if not report:
            return None

        return Hypothesis(
            minister=self.name,
            predicted_signals=list(report.predicted_signals or []),
            matched_signals=[],
            missing_signals=[],
            coverage=max(0.0, min(1.0, float(report.confidence or 0.0))),
            dimension=self._dimension(),
        )

    def _create_report(
        self,
        predicted: List[str],
        confidence: float,
        *,
        classification_source: str = "llm",
        reasoning_source: str = "pending",
        classification_degraded: bool = False,
        reasoning_degraded: bool = False,
        degradation_reason: str = "",
    ) -> MinisterReport:
        report = MinisterReport(
            minister_name=self.name,
            predicted_signals=list(predicted or []),
            confidence=max(0.0, min(1.0, float(confidence))),
            classification_source=classification_source,
            reasoning_source=reasoning_source,
            classification_degraded=classification_degraded,
            reasoning_degraded=reasoning_degraded,
            degradation_reasons=[degradation_reason] if degradation_reason else [],
        )
        return report

    @staticmethod
    def _append_degradation_reason(report: MinisterReport, reason: str) -> None:
        note = str(reason or "").strip()
        if note and note not in report.degradation_reasons:
            report.degradation_reasons.append(note)

    def _apply_deterministic_reasoning(
        self,
        report: MinisterReport,
        full_context,
        *,
        reason: str,
    ) -> MinisterReport:
        escalation = _as_float(getattr(full_context, "escalation_score", 0.0), 0.0)
        contradictions = list(getattr(full_context, "contradictions", []) or [])
        gaps = list(getattr(full_context, "gaps", []) or [])
        pressures = getattr(full_context, "pressures", {}) or {}

        top_pressures = [
            f"{k}={float(v):.2f}"
            for k, v in sorted((pressures or {}).items(), key=lambda item: -_as_float(item[1], 0.0))[:3]
            if _as_float(v, 0.0) > 0.0
        ]
        signal_drivers = [sig.replace("SIG_", "").replace("_", " ").lower() for sig in list(report.predicted_signals or [])[:3]]
        drivers = top_pressures + signal_drivers
        if not drivers:
            drivers = [f"deterministic fallback triggered because {reason}"]

        counterarguments = contradictions[:2]
        if not counterarguments:
            if escalation < 0.35:
                counterarguments = ["Base escalation score remains low despite selected signals."]
            else:
                counterarguments = ["Fallback reasoning limits confidence in this minister's adjustment."]

        if gaps:
            critical_gaps = gaps[:3]
        else:
            critical_gaps = ["Higher-quality dated evidence is still needed for this domain."]

        if escalation >= 0.65 and report.predicted_signals:
            adjustment = "increase"
            modifier = 0.02
        elif escalation <= 0.25 and not report.predicted_signals:
            adjustment = "decrease"
            modifier = -0.02
        else:
            adjustment = "maintain"
            modifier = 0.0

        report.risk_level_adjustment = adjustment
        report.primary_drivers = [str(item)[:200] for item in drivers[:5]]
        report.critical_gaps = [str(item)[:200] for item in critical_gaps[:5]]
        report.counterarguments = [str(item)[:200] for item in counterarguments[:5]]
        report.confidence_modifier = modifier
        report.reasoning_text = f"Deterministic reasoning fallback: {reason}"[:1000]
        report.reasoning_source = "deterministic"
        report.reasoning_degraded = True
        report.justification_strength = 0.45
        self._append_degradation_reason(report, reason)
        return report

    def _flight_component_name(self) -> str:
        token = str(self.name or "").lower()
        if "security" in token:
            return "MINISTER_SECURITY"
        if "economic" in token:
            return "MINISTER_ECONOMIC"
        if "domestic" in token:
            return "MINISTER_DOMESTIC"
        if "diplomatic" in token:
            return "MINISTER_DIPLOMATIC"
        return f"MINISTER_{str(self.name or 'UNKNOWN').upper().replace(' ', '_')}"

    def _build_system_prompt(self, allowed_signals: List[str]) -> str:
        allowed_block = "\n".join(allowed_signals)
        return (
            "You are NOT an analyst.\n"
            "You are a classification engine.\n\n"
            "Your job is to label whether each signal is PRESENT or ABSENT "
            "based ONLY on numeric state values.\n\n"
            "Rules:\n"
            "- Do NOT write explanations.\n"
            "- Do NOT infer geopolitics.\n"
            "- Do NOT speculate.\n"
            "- Only check thresholds.\n"
            "- predicted_signals MUST contain only allowed tokens.\n"
            "- If none are present, return an empty list.\n\n"
            "Return STRICT JSON ONLY. NO TEXT. EXACT SHAPE:\n"
            "{\n"
            '  "predicted_signals": ["SIGNAL_TOKENS_ONLY"],\n'
            '  "matched_signals": ["(optional) subset that meet numeric thresholds"],\n'
            '  "missing_signals": ["(optional) signals that are not met"],\n'
            '  \"dimension\": \"CAPABILITY|INTENT|STABILITY|COST|UNKNOWN\",\n'
            '  "confidence": 0.0\n'
            "}\n"
            "Do not add extra keys or commentary.\n\n"
            "Allowed signals (choose ONLY from this list):\n"
            f"{allowed_block}"
        )

    @staticmethod
    def _classification_output_schema() -> str:
        return (
            '{\n'
            '  "predicted_signals": ["SIGNAL_TOKENS_ONLY"],\n'
            '  "matched_signals": ["optional subset"],\n'
            '  "missing_signals": ["optional unmet signals"],\n'
            '  "dimension": "CAPABILITY|INTENT|STABILITY|COST|UNKNOWN",\n'
            '  "confidence": 0.0\n'
            '}'
        )

    @staticmethod
    def _reasoning_output_schema() -> str:
        return (
            '{\n'
            '  "risk_level_adjustment": "increase|decrease|maintain",\n'
            '  "primary_drivers": ["driver 1", "driver 2"],\n'
            '  "critical_gaps": ["gap 1"],\n'
            '  "counterarguments": ["counterargument 1"],\n'
            '  "confidence_modifier": 0.0,\n'
            '  "justification_strength": 0.5,\n'
            '  "rationale": "<= 150 words"\n'
            '}'
        )

    @staticmethod
    def _build_state_values_block(state_context: StateContext) -> str:
        mobilization = _as_float(
            _pick(state_context, "military.mobilization", _pick(state_context, "military.mobilization_level", 0.0)),
            0.0,
        )
        exercises = _as_float(_pick(state_context, "military.exercises", 0.0), 0.0)
        hostility = _as_float(
            _pick(state_context, "diplomatic.hostility", _pick(state_context, "diplomatic.hostility_tone", 0.0)),
            0.0,
        )
        trade_dependency = _as_float(_pick(state_context, "economic.trade_dependency", 0.0), 0.0)
        cyber = _pick(
            state_context,
            "capabilities.cyber",
            _pick(state_context, "capability.cyber_activity", _pick(state_context, "capabilities.cyber_activity", "none")),
        )
        logistics = _pick(
            state_context,
            "capabilities.logistics",
            _pick(state_context, "capability.logistics_activity", _pick(state_context, "capabilities.logistics_activity", "none")),
        )
        alliances = _as_float(
            _pick(state_context, "diplomatic.alliance_activity", _pick(state_context, "diplomatic.alliances", 0.0)),
            0.0,
        )
        negotiations = _as_float(_pick(state_context, "diplomatic.negotiations", 0.0), 0.0)
        sanctions = _as_float(
            _pick(state_context, "economic.sanctions_pressure", _pick(state_context, "economic.sanctions", 0.0)),
            0.0,
        )
        economic_pressure = _as_float(_pick(state_context, "economic.economic_pressure", 0.0), 0.0)

        # Include strategic pressure indices when available
        pressure_block = ""
        raw_pressures = getattr(state_context, "pressures", {}) or {}
        if raw_pressures:
            if hasattr(raw_pressures, "to_dict"):
                try:
                    raw_pressures = raw_pressures.to_dict()
                except Exception:
                    pass
            if isinstance(raw_pressures, dict):
                ip = max(0.0, min(1.0, float(raw_pressures.get("intent_pressure", 0.0) or 0.0)))
                cp = max(0.0, min(1.0, float(raw_pressures.get("capability_pressure", 0.0) or 0.0)))
                sp = max(0.0, min(1.0, float(raw_pressures.get("stability_pressure", 0.0) or 0.0)))
                ep = max(0.0, min(1.0, float(raw_pressures.get("economic_pressure", 0.0) or 0.0)))
                pressure_block = (
                    "\n\nSTRATEGIC PRESSURES:\n"
                    f"IntentPressure={ip:.3f}\n"
                    f"CapabilityPressure={cp:.3f}\n"
                    f"StabilityPressure={sp:.3f}\n"
                    f"EconomicPressure={ep:.3f}"
                )

        return (
            "STATE VALUES:\n"
            f"Mobilization={mobilization:.3f}\n"
            f"Exercises={exercises:.3f}\n"
            f"HostilityTone={hostility:.3f}\n"
            f"TradeDependency={trade_dependency:.3f}\n"
            f"AllianceActivity={alliances:.3f}\n"
            f"Negotiations={negotiations:.3f}\n"
            f"SanctionsPressure={sanctions:.3f}\n"
            f"EconomicPressure={economic_pressure:.3f}\n"
            f"CyberCapability={cyber}\n"
            f"LogisticsActivity={logistics}"
            f"{pressure_block}"
        )

    @staticmethod
    def _clean_response(raw: str) -> str:
        text = str(raw or "")
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        # Extract content from code fences anywhere in the text
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
        elif text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _parse_response_json(self, raw: str) -> Optional[Dict[str, Any]]:
        text = self._clean_response(raw)
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except Exception:
            # Fallback: find outermost { ... } block
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                try:
                    parsed = json.loads(text[start : end + 1])
                except Exception:
                    return None
            else:
                return None
        return parsed if isinstance(parsed, dict) else None

    def _normalize_predicted_signals(self, values: Any) -> List[str]:
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            values = []

        normalized: List[str] = []
        seen = set()
        for item in values:
            token = _as_signal_token(item)
            # Fix 4: Accept signals in EITHER the allowed set OR the
            # ontology (not AND).  The double gate silently dropped valid
            # signals when one list was incomplete.
            if token not in _ALLOWED_SIGNAL_SET and token not in SIGNAL_ONTOLOGY:
                continue
            if token in seen:
                continue
            seen.add(token)
            normalized.append(token)
            if len(normalized) >= self.MAX_PREDICTED_SIGNALS:
                break
        return normalized

    def _normalized_confidence(self, predicted_signals: List[str]) -> float:
        if not self.allowed_signals:
            return 0.0
        return max(0.0, min(1.0, float(len(predicted_signals)) / float(len(self.allowed_signals))))

    def _pressure_classify(self, state_context: StateContext) -> Optional[MinisterReport]:
        """
        Pressure-based fallback classification.
        Override in subclass for dimension-specific pressure logic.
        Falls back to generic deterministic thresholds if not overridden.
        """
        data = self._deterministic_fallback(state_context)
        return self._create_report(
            predicted=data["predicted_signals"],
            confidence=data["confidence"],
            classification_source="deterministic",
            classification_degraded=True,
            degradation_reason="generic deterministic classification fallback",
        )

    def _deterministic_fallback(self, state_context: StateContext) -> Dict[str, Any]:
        """Fix 4: Lowered thresholds to realistic levels.

        With upstream signal confidence at 0.10-0.40, the previous
        thresholds (mobilization>0.70, hostility>0.75) were unreachable.
        These thresholds now match the signal levels the system actually
        produces, so ministers generate meaningful hypotheses.
        """
        signals: List[str] = []

        mobilization = _as_float(
            _pick(state_context, "military.mobilization", _pick(state_context, "military.mobilization_level", 0.0)),
            0.0,
        )
        hostility = _as_float(
            _pick(state_context, "diplomatic.hostility", _pick(state_context, "diplomatic.hostility_tone", 0.0)),
            0.0,
        )
        negotiations = _as_float(_pick(state_context, "diplomatic.negotiations", 0.0), 0.0)
        alliances = _as_float(
            _pick(state_context, "diplomatic.alliance_activity", _pick(state_context, "diplomatic.alliances", 0.0)),
            0.0,
        )
        sanctions = _as_float(
            _pick(state_context, "economic.sanctions_pressure", _pick(state_context, "economic.sanctions", 0.0)),
            0.0,
        )
        economic_pressure = _as_float(_pick(state_context, "economic.economic_pressure", 0.0), 0.0)
        cyber = _pick(
            state_context,
            "capabilities.cyber",
            _pick(state_context, "capability.cyber_activity", _pick(state_context, "capabilities.cyber_activity", "none")),
        )
        logistics = _pick(
            state_context,
            "capabilities.logistics",
            _pick(state_context, "capability.logistics_activity", _pick(state_context, "capabilities.logistics_activity", "none")),
        )

        # Fix 4: Thresholds lowered to match real signal levels
        if mobilization > 0.20:
            signals.append("SIG_MIL_ESCALATION")
        if mobilization > 0.15:
            signals.append("SIG_MIL_MOBILIZATION")
        if _is_high_token(cyber) or _as_float(cyber, 0.0) > 0.30:
            signals.append("SIG_CYBER_ACTIVITY")
        if hostility > 0.35:
            signals.append("SIG_DIP_HOSTILITY")
        if alliances > 0.25:
            signals.append("SIG_ALLIANCE_ACTIVATION")
        if sanctions > 0.30 or economic_pressure > 0.30:
            signals.append("SIG_ECONOMIC_PRESSURE")
        if mobilization > 0.20 and hostility > 0.25:
            signals.append("SIG_FORCE_POSTURE")
        if _is_high_token(logistics) or mobilization > 0.25:
            signals.append("SIG_LOGISTICS_PREP")
        if mobilization > 0.15 and negotiations < 0.40:
            signals.append("SIG_DECEPTION_ACTIVITY")
        if hostility > 0.30 and negotiations < 0.30:
            signals.append("SIG_NEGOTIATION_BREAKDOWN")
        if hostility > 0.25:
            signals.append("SIG_COERCIVE_BARGAINING")

        predicted = self._normalize_predicted_signals(signals)
        return {
            "predicted_signals": predicted,
            "confidence": self._normalized_confidence(predicted),
        }

    # ══════════════════════════════════════════════════════════════
    #  REASONING PASS — Full-context cognitive deliberation
    # ══════════════════════════════════════════════════════════════

    def _build_reasoning_prompt(self, synthesis_summary: str = "") -> str:
        """
        System prompt for the reasoning pass. Unlike the classification
        prompt ("you are NOT an analyst"), this one says "you ARE".
        """
        role_dim, role_focus = ROLE_FOCUS.get(
            self.name, ("UNKNOWN", "Analyse all available dimensions."),
        )

        round_instruction = ""
        if synthesis_summary:
            round_instruction = (
                "\n\nYou are now in ROUND 2 of deliberation.\n"
                "A synthesis of all Round-1 minister assessments is provided below.\n"
                "You may revise your position if the synthesis reveals something you missed,\n"
                "but do NOT conform simply because others disagree — defend your view if\n"
                "you believe it is correct.\n\n"
                f"ROUND 1 SYNTHESIS:\n{synthesis_summary}\n"
            )

        return (
            f"You are the {self.name} on an intelligence analysis council.\n"
            f"Your domain is {role_dim}.\n\n"
            f"{role_focus}\n\n"
            "You are given the full state of the world: pressures, projected signals,\n"
            "trajectory forecast, conflict state probabilities, structural gaps,\n"
            "contradictions, and escalation score.\n\n"
            "Your task is to REASON about what this information means for escalation risk\n"
            "from your domain perspective. You must:\n"
            "1. Identify the primary drivers of risk in your domain\n"
            "2. Flag any critical intelligence gaps\n"
            "3. Generate at least one counterargument against your own assessment\n"
            "4. Recommend whether risk should increase, decrease, or be maintained\n"
            "5. Suggest a confidence modifier between -0.10 and +0.10\n"
            "6. Provide a compact rationale inside the JSON field `rationale` in 150 words or fewer\n\n"
            "Return STRICT JSON ONLY. NO TEXT OUTSIDE JSON.\n"
            "Put the structured answer first and keep it complete even if you omit optional reasoning.\n"
            "Do not add extra keys or commentary.\n"
            f"{self._reasoning_output_schema()}\n"
            f"{round_instruction}"
        )

    @staticmethod
    def _build_full_context_block(full_context) -> str:
        """Serialise FullContext into a text block for the LLM prompt."""
        from engine.Layer4_Analysis.council_session import FullContext
        if not isinstance(full_context, FullContext):
            return "NO CONTEXT AVAILABLE"

        lines = ["FULL STATE CONTEXT:"]

        # Pressures
        p = full_context.pressures or {}
        if p:
            lines.append("\nSTRATEGIC PRESSURES:")
            for k, v in sorted(p.items()):
                lines.append(f"  {k} = {v:.3f}")

        # Signal confidence
        sc = full_context.signal_confidence or {}
        if sc:
            lines.append("\nSIGNAL CONFIDENCE (top signals):")
            for name, conf in sorted(sc.items(), key=lambda x: -x[1])[:12]:
                lines.append(f"  {name} = {conf:.3f}")

        # Trajectory
        t = full_context.trajectory or {}
        if t:
            lines.append("\nTRAJECTORY FORECAST:")
            for k in ("prob_up", "prob_down", "prob_stable", "expansion_mode",
                       "pre_war_warning", "velocity"):
                if k in t:
                    lines.append(f"  {k} = {t[k]}")

        # Conflict state probabilities
        sp = full_context.state_probabilities or {}
        if sp:
            lines.append("\nCONFLICT STATE PROBABILITIES:")
            for s, v in sorted(sp.items(), key=lambda x: -x[1]):
                lines.append(f"  {s} = {v:.3f}")

        # Escalation score
        lines.append(f"\nESCALATION SCORE (SRE): {full_context.escalation_score:.3f}")

        # Gaps
        if full_context.gaps:
            lines.append("\nSTRUCTURAL GAPS DETECTED:")
            for g in full_context.gaps[:6]:
                lines.append(f"  - {g}")

        # Contradictions
        if full_context.contradictions:
            lines.append("\nCONTRADICTIONS DETECTED:")
            for c in full_context.contradictions[:4]:
                lines.append(f"  - {c}")

        return "\n".join(lines)

    def reason(
        self,
        full_context,
        report: MinisterReport,
        synthesis_summary: str = "",
        session: Any | None = None,
    ) -> MinisterReport:
        """
        Reasoning pass (second LLM call).

        Receives the FullContext snapshot + the minister's own classification
        report from pass 1.  Returns the same report object enriched with
        reasoning fields (risk_level_adjustment, primary_drivers, etc.).

        If the LLM fails, reasoning fields stay at safe defaults and the
        classification results are still valid.
        """
        effort = decide_effort(session, full_context) if session is not None else None
        system_prompt = self._build_reasoning_prompt(synthesis_summary)
        if effort is not None:
            system_prompt = f"{system_prompt.rstrip()}\n\n{effort.prompt_instruction}"
        reasoning_max_tokens_raw = str(os.getenv("MINISTER_REASONING_MAX_TOKENS", "")).strip()
        reasoning_max_tokens = int(reasoning_max_tokens_raw) if reasoning_max_tokens_raw else None
        task_type = "round2_reasoning" if synthesis_summary else "minister_reasoning"

        try:
            next_attempt_budget: Optional[int] = None
            last_reasoning_prompt: Dict[str, Any] = {}
            last_reasoning_response = ""
            last_reasoning_parsed: Optional[Dict[str, Any]] = None
            for attempt_idx in range(2):
                if session is not None:
                    pack = build_minister_reasoning_pack(
                        minister_name=self.name,
                        session=session,
                        full_context=full_context,
                        report=report,
                        synthesis_summary=synthesis_summary,
                        output_schema=self._reasoning_output_schema(),
                    )
                    prompt_text = pack.render()
                    max_budget = int(pack.output_budget or 0) or reasoning_max_tokens
                else:
                    pack = None
                    prompt_text = self._build_full_context_block(full_context)
                    max_budget = reasoning_max_tokens
                if effort is not None:
                    report.effort_level = effort.level
                stage_budget = recommend_stage_output_budget(
                    task_type,
                    int(max_budget or 0) or int(reasoning_max_tokens or 0) or 3000,
                    effort=effort,
                )
                if stage_budget > 0:
                    max_budget = stage_budget
                hard_budget_cap = max(256, int(pack.output_budget or 0) if pack is not None else int(reasoning_max_tokens or max_budget or 3000))
                if next_attempt_budget is not None:
                    max_budget = max(256, min(hard_budget_cap, int(next_attempt_budget)))

                attempt_system_prompt = system_prompt
                soft_budget_instruction = stage_budget_instruction(task_type, effort=effort)
                if soft_budget_instruction:
                    attempt_system_prompt = f"{attempt_system_prompt.rstrip()}\n\n{soft_budget_instruction}"
                if attempt_idx == 1:
                    attempt_system_prompt = (
                        attempt_system_prompt.rstrip()
                        + "\n\nRetry mode: return only the compact JSON object. "
                          "Keep every required field complete. Improve only the flagged issues. "
                          "Do not expand reasoning unnecessarily."
                    )
                    if max_budget:
                        max_budget = max(256, int(max_budget * 0.7))

                last_reasoning_prompt = {
                    "task_type": task_type,
                    "attempt": attempt_idx + 1,
                    "system_prompt": attempt_system_prompt,
                    "user_prompt": prompt_text,
                    "max_tokens": int(max_budget or 0),
                    "pack": (
                        {
                            "input_budget": int(pack.input_budget or 0),
                            "output_budget": int(pack.output_budget or 0),
                            "estimated_tokens": int(getattr(pack, "estimated_tokens", 0) or 0),
                            "dropped_sections": list(getattr(pack, "dropped_sections", []) or []),
                            "overflow": bool(getattr(pack, "overflow", False)),
                        }
                        if pack is not None
                        else {}
                    ),
                }
                response = self.llm.generate(
                    attempt_system_prompt,
                    prompt_text,
                    temperature=0.1,
                    json_mode=True,
                    max_tokens=max_budget,
                    task_type=task_type,
                    context_pack=pack,
                )
                last_reasoning_response = str(response)

                parsed = self._parse_response_json(response)
                if not isinstance(parsed, dict):
                    logger.warning(
                        "[Minister:%s] Reasoning JSON parse failed on attempt %d; raw='%s'",
                        self.name,
                        attempt_idx + 1,
                        str(response)[:200],
                    )
                    continue

                last_reasoning_parsed = dict(parsed)
                adj = str(parsed.get("risk_level_adjustment", "maintain")).lower().strip()
                if adj not in ("increase", "decrease", "maintain"):
                    adj = "maintain"
                report.risk_level_adjustment = adj
                report.primary_drivers = [
                    str(d)[:200] for d in (parsed.get("primary_drivers") or [])
                    if str(d).strip()
                ][:5]
                report.critical_gaps = [
                    str(g)[:200] for g in (parsed.get("critical_gaps") or [])
                    if str(g).strip()
                ][:5]
                report.counterarguments = [
                    str(c)[:200] for c in (parsed.get("counterarguments") or [])
                    if str(c).strip()
                ][:5]
                mod = float(parsed.get("confidence_modifier", 0.0) or 0.0)
                report.confidence_modifier = max(-0.10, min(0.10, mod))
                report.justification_strength = max(
                    0.10,
                    min(0.95, float(parsed.get("justification_strength", 0.5) or 0.5)),
                )
                rationale = str(parsed.get("rationale", "") or "").strip()
                if rationale:
                    report.reasoning_text = rationale[:1000]
                else:
                    report.reasoning_text = json.dumps(parsed, ensure_ascii=True)[:1000]
                report.reasoning_source = "llm"
                report.reasoning_degraded = False
                setattr(report, "reasoning_prompt", last_reasoning_prompt)
                setattr(report, "reasoning_response", last_reasoning_response)
                setattr(report, "reasoning_parsed", last_reasoning_parsed)

                analysis = analyze_output(
                    output_text=response,
                    structured=parsed,
                    max_tokens=int(max_budget or 0),
                    predicted_signals=report.predicted_signals,
                    confidence=report.justification_strength,
                )
                report.reasoning_quality_score = float(analysis.quality_score)
                report.reasoning_signal_density = float(analysis.signal_density)
                report.reasoning_length_ratio = float(analysis.length_ratio)
                report.overthinking_detected = bool(analysis.overthinking)
                report.underthinking_detected = bool(analysis.underthinking)
                report.reasoning_monitor_issues = list(analysis.issues)

                critique = critique_minister_output(parsed, report, full_context)
                report.self_critique_issues = list(critique.critical_issues)
                needs_retry = bool(critique.should_retry or analysis.should_retry)
                if needs_retry and attempt_idx == 0:
                    feedback_parts: List[str] = []
                    if critique.should_retry:
                        feedback_parts.append(build_improvement_feedback(critique))
                    if analysis.should_retry:
                        feedback_parts.append(build_adjustment_feedback(analysis))
                    feedback = "\n\n".join(part for part in feedback_parts if str(part).strip())
                    if feedback:
                        system_prompt = f"{system_prompt.rstrip()}\n\n{feedback}"
                    next_attempt_budget = recommend_adjusted_budget(
                        int(max_budget or 0) or hard_budget_cap,
                        hard_cap=hard_budget_cap,
                        analysis=analysis,
                    )
                    report.self_critique_applied = True
                    logger.info(
                        "[Minister:%s] Bounded retry requested: critique=%s monitor=%s next_budget=%s",
                        self.name,
                        critique.critical_issues,
                        analysis.issues,
                        next_attempt_budget,
                    )
                    continue
                if needs_retry and attempt_idx == 1:
                    logger.warning(
                        "[Minister:%s] Post-retry reasoning issues remain: critique=%s monitor=%s",
                        self.name,
                        critique.critical_issues,
                        analysis.issues,
                    )
                    break

                if max_budget and estimate_tokens(response) >= max(64, int(max_budget * 0.95)) and attempt_idx == 0:
                    logger.info(
                        "[Minister:%s] Reasoning response was near budget; retrying once with tighter structure.",
                        self.name,
                    )
                    continue

                logger.info(
                    "[Minister:%s] Reasoning: adj=%s  drivers=%d  gaps=%d  counter=%d  mod=%+.3f",
                    self.name, report.risk_level_adjustment,
                    len(report.primary_drivers), len(report.critical_gaps),
                    len(report.counterarguments), report.confidence_modifier,
                )
                return report

            note_llm_deterministic_fallback(f"minister_reasoning:{self.name}")
            fallback = self._apply_deterministic_reasoning(
                report,
                full_context,
                reason="reasoning JSON parse failure",
            )
            setattr(fallback, "reasoning_prompt", last_reasoning_prompt)
            setattr(fallback, "reasoning_response", last_reasoning_response)
            setattr(fallback, "reasoning_parsed", last_reasoning_parsed)
            return fallback
        except Exception as exc:
            logger.warning("[Minister:%s] Reasoning pass failed: %s", self.name, exc)
            note_llm_deterministic_fallback(f"minister_reasoning:{self.name}")
            fallback = self._apply_deterministic_reasoning(
                report,
                full_context,
                reason=f"reasoning exception: {exc}",
            )
            setattr(fallback, "reasoning_prompt", locals().get("last_reasoning_prompt", {}))
            setattr(fallback, "reasoning_response", locals().get("last_reasoning_response", ""))
            setattr(fallback, "reasoning_parsed", locals().get("last_reasoning_parsed", None))
            return fallback

    @staticmethod
    def _resolve_pressures(state_context: StateContext) -> Dict[str, float]:
        raw = getattr(state_context, "pressures", {}) or {}
        if hasattr(raw, "to_dict"):
            try:
                raw = raw.to_dict()
            except Exception:
                raw = {}
        if not isinstance(raw, dict):
            raw = {
                "intent_pressure": _as_float(getattr(raw, "intent_pressure", 0.0), 0.0),
                "capability_pressure": _as_float(getattr(raw, "capability_pressure", 0.0), 0.0),
                "stability_pressure": _as_float(getattr(raw, "stability_pressure", 0.0), 0.0),
                "economic_pressure": _as_float(getattr(raw, "economic_pressure", 0.0), 0.0),
            }

        return {
            "intent_pressure": max(0.0, min(1.0, _as_float(raw.get("intent_pressure", 0.0), 0.0))),
            "capability_pressure": max(0.0, min(1.0, _as_float(raw.get("capability_pressure", 0.0), 0.0))),
            "stability_pressure": max(0.0, min(1.0, _as_float(raw.get("stability_pressure", 0.0), 0.0))),
            "economic_pressure": max(0.0, min(1.0, _as_float(raw.get("economic_pressure", 0.0), 0.0))),
        }

    def _pressure_report(
        self,
        *,
        pressure_value: float,
        high_signals: List[str],
        medium_signals: List[str],
        low_signals: List[str] | None = None,
        high_threshold: float = 0.70,
        medium_threshold: float = 0.45,
        low_threshold: float = 0.30,
        state_context: Optional[StateContext] = None,
    ) -> MinisterReport:
        level = max(0.0, min(1.0, float(pressure_value or 0.0)))

        # ── Temporal trend adjustment ─────────────────────────────
        # If the trend briefing shows signals in this minister's
        # domain are RISING or ESCALATING, lower the activation
        # threshold by up to 0.15 — wars start from buildup.
        trend_boost = 0.0
        trend_notes: List[str] = []
        if state_context is not None:
            briefing = getattr(state_context, "trend_briefing", {}) or {}
            escalation_patterns = getattr(state_context, "escalation_patterns", []) or []

            # Check if any of this minister's signals show trend concern
            all_candidate_signals = set(high_signals or []) | set(medium_signals or [])
            if low_signals:
                all_candidate_signals |= set(low_signals)

            for sig in all_candidate_signals:
                ind = briefing.get(sig, {})
                if not ind:
                    continue
                momentum_label = ind.get("momentum_label", "stable")
                persistence_label = ind.get("persistence_label", "noise")
                momentum = float(ind.get("momentum", 0.0))
                spike = bool(ind.get("spike", False))

                # Escalation pattern: significant threshold reduction
                if sig in escalation_patterns:
                    trend_boost = max(trend_boost, 0.15)
                    trend_notes.append(f"{sig}: ESCALATION PATTERN")
                elif momentum_label == "rapid_escalation":
                    trend_boost = max(trend_boost, 0.12)
                    trend_notes.append(f"{sig}: rapid escalation (m={momentum:+.2f})")
                elif momentum_label == "rising" and persistence_label in ("pattern", "sustained"):
                    trend_boost = max(trend_boost, 0.08)
                    trend_notes.append(f"{sig}: rising+persistent")
                elif spike:
                    trend_boost = max(trend_boost, 0.10)
                    trend_notes.append(f"{sig}: SPIKE detected")

            if trend_notes:
                logger.info(
                    "[Minister:%s] Trend adjustment: boost=%.2f — %s",
                    self.name, trend_boost, "; ".join(trend_notes),
                )

        # Apply trend boost: effectively lower thresholds
        effective_high = max(0.20, high_threshold - trend_boost)
        effective_med = max(0.15, medium_threshold - trend_boost)
        effective_low = max(0.10, low_threshold - trend_boost)

        chosen: List[str] = []
        if level >= effective_high:
            chosen = list(high_signals or [])
        elif level >= effective_med:
            chosen = list(medium_signals or [])
        elif low_signals and level >= effective_low:
            chosen = list(low_signals or [])

        normalized = self._normalize_predicted_signals(chosen)
        confidence = level if normalized else 0.0
        return self._create_report(
            predicted=normalized,
            confidence=confidence,
            classification_source="pressure",
            classification_degraded=True,
            degradation_reason="pressure-based classification fallback",
        )

    def _ask_llm(
        self,
        *,
        state_context: StateContext,
        specific_instructions: str,
    ) -> Optional[MinisterReport]:
        """
        Closed-world classification: strict JSON only, with one retry and deterministic fallback on format breach.
        """
        system_prompt = self._build_system_prompt(self.allowed_signals)
        attempts: List[str] = []
        parsed: Optional[Dict[str, Any]] = None
        last_prompt_payload: Dict[str, Any] = {}
        last_response_text = ""
        last_parsed_payload: Optional[Dict[str, Any]] = None

        for attempt_idx in range(2):
            attempt_specific_instructions = specific_instructions
            if attempt_idx == 1:
                attempt_specific_instructions = (
                    f"{specific_instructions}\n"
                    "Retry mode: return only the JSON object with the required keys. "
                    "No explanation, no prose, no markdown."
                )

            pack = build_minister_classification_pack(
                minister_name=self.name,
                state_context=state_context,
                specific_instructions=attempt_specific_instructions,
                output_schema=self._classification_output_schema(),
                question="",
            )
            user_prompt = pack.render()
            last_prompt_payload = {
                "task_type": "classification",
                "attempt": attempt_idx + 1,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "pack": {
                    "input_budget": int(pack.input_budget or 0),
                    "output_budget": int(pack.output_budget or 0),
                    "estimated_tokens": int(getattr(pack, "estimated_tokens", 0) or 0),
                    "dropped_sections": list(getattr(pack, "dropped_sections", []) or []),
                    "overflow": bool(getattr(pack, "overflow", False)),
                },
            }
            response = self.llm.generate(
                system_prompt,
                user_prompt,
                temperature=0.0,
                json_mode=True,
                max_tokens=int(pack.output_budget or 0) or None,
                task_type="classification",
                context_pack=pack,
            )
            last_response_text = str(response)
            attempts.append(str(response))

            if str(response).startswith("LLM_ERROR:"):
                logger.warning(
                    "[Minister:%s] LLM_ERROR on attempt %d: %s",
                    self.name,
                    attempt_idx + 1,
                    str(response)[:200],
                )
                continue

            parsed = self._parse_response_json(response)
            if isinstance(parsed, dict):
                last_parsed_payload = dict(parsed)
                if int(pack.output_budget or 0) > 0 and estimate_tokens(response) >= max(64, int(pack.output_budget * 0.95)) and attempt_idx == 0:
                    logger.info(
                        "[Minister:%s] Classification response was near budget; retrying once with tighter structure.",
                        self.name,
                    )
                    parsed = None
                    continue
                break

            logger.warning(
                "[Minister:%s] JSON parse failed on attempt %d; raw='%s'",
                self.name,
                attempt_idx + 1,
                self._clean_response(response)[:240],
            )

        if not isinstance(parsed, dict):
            logger.warning(
                "[Minister:%s] LLM failed after %d attempts — using pressure-based fallback; last_raw='%s'",
                self.name,
                len(attempts),
                self._clean_response(attempts[-1] if attempts else "")[:240],
            )
            note_llm_deterministic_fallback(f"minister:{self.name}")
            fallback_report = self._pressure_classify(state_context)
            if fallback_report is not None:
                setattr(fallback_report, "classification_prompt", last_prompt_payload)
                setattr(fallback_report, "classification_response", last_response_text or (attempts[-1] if attempts else ""))
                setattr(fallback_report, "classification_parsed", last_parsed_payload)
                return fallback_report
            # Last resort: generic deterministic
            data = self._deterministic_fallback(state_context)
            deterministic_report = self._create_report(
                predicted=data["predicted_signals"],
                confidence=data["confidence"],
                classification_source="deterministic",
                classification_degraded=True,
                degradation_reason="deterministic classification fallback after repeated LLM failure",
            )
            setattr(deterministic_report, "classification_prompt", last_prompt_payload)
            setattr(deterministic_report, "classification_response", last_response_text or (attempts[-1] if attempts else ""))
            setattr(deterministic_report, "classification_parsed", last_parsed_payload)
            return deterministic_report

        predicted = self._normalize_predicted_signals(parsed.get("predicted_signals", []))
        confidence = self._normalized_confidence(predicted)
        final_report = self._create_report(
            predicted=predicted,
            confidence=confidence,
            classification_source="llm",
        )
        setattr(final_report, "classification_prompt", last_prompt_payload)
        setattr(final_report, "classification_response", last_response_text)
        setattr(final_report, "classification_parsed", last_parsed_payload or dict(parsed or {}))
        return final_report
