from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


@dataclass(frozen=True)
class EffortDecision:
    level: str
    complexity: float
    uncertainty: float
    score: float
    recommended_max_tokens: int
    prompt_instruction: str


def estimate_complexity(session: Any, full_context: Any) -> float:
    signal_count = len(dict(getattr(full_context, "signal_confidence", {}) or {}))
    actors = getattr(getattr(getattr(session, "state_context", None), "actors", None), "__dict__", {}) or {}
    actor_count = len([value for value in actors.values() if str(value or "").strip()])
    contradiction_count = len(list(getattr(full_context, "contradictions", []) or []))
    gap_count = len(list(getattr(full_context, "gaps", []) or []))
    escalation = _safe_float(getattr(full_context, "escalation_score", 0.0), 0.0)

    score = (
        min(1.0, signal_count / 12.0) * 0.30
        + min(1.0, actor_count / 3.0) * 0.15
        + min(1.0, contradiction_count / 4.0) * 0.20
        + min(1.0, gap_count / 4.0) * 0.15
        + max(0.0, min(1.0, escalation)) * 0.20
    )
    return max(0.0, min(1.0, score))


def estimate_uncertainty(session: Any, full_context: Any) -> float:
    signal_conf = list(dict(getattr(full_context, "signal_confidence", {}) or {}).values())
    avg_signal_conf = sum(_safe_float(value, 0.0) for value in signal_conf) / max(1, len(signal_conf))
    hypothesis_coverages = [
        max(0.0, min(1.0, _safe_float(getattr(hypothesis, "coverage", 0.0), 0.0)))
        for hypothesis in list(getattr(session, "hypotheses", []) or [])
    ]
    avg_coverage = sum(hypothesis_coverages) / max(1, len(hypothesis_coverages)) if hypothesis_coverages else 0.0
    contradictions = len(list(getattr(full_context, "contradictions", []) or []))
    gaps = len(list(getattr(full_context, "gaps", []) or []))

    score = (
        (1.0 - avg_signal_conf) * 0.35
        + (1.0 - avg_coverage) * 0.35
        + min(1.0, contradictions / 4.0) * 0.15
        + min(1.0, gaps / 4.0) * 0.15
    )
    return max(0.0, min(1.0, score))


def decide_effort(session: Any, full_context: Any) -> EffortDecision:
    complexity = estimate_complexity(session, full_context)
    uncertainty = estimate_uncertainty(session, full_context)
    score = max(0.0, min(1.0, (0.6 * complexity) + (0.4 * uncertainty)))

    if score < 0.30:
        level = "low"
        max_tokens = 1200
        instruction = (
            "Effort Level: LOW. Give a direct structured answer only. "
            "Keep rationale under 120 words and do not use the full token budget unnecessarily."
        )
    elif score < 0.70:
        level = "medium"
        max_tokens = 2400
        instruction = (
            "Effort Level: MEDIUM. Reason carefully but stay concise and structured. "
            "Keep rationale under 220 words and avoid narrative expansion."
        )
    else:
        level = "high"
        max_tokens = 3000
        instruction = (
            "Effort Level: HIGH. Use deeper reasoning, but remain concise and keep the structured answer complete. "
            "Keep rationale under 300 words and do not spend tokens on repetition."
        )

    return EffortDecision(
        level=level,
        complexity=complexity,
        uncertainty=uncertainty,
        score=score,
        recommended_max_tokens=max_tokens,
        prompt_instruction=instruction,
    )


def effort_metadata(decision: EffortDecision) -> Dict[str, Any]:
    return {
        "level": decision.level,
        "complexity": round(decision.complexity, 4),
        "uncertainty": round(decision.uncertainty, 4),
        "score": round(decision.score, 4),
        "recommended_max_tokens": int(decision.recommended_max_tokens),
    }


def recommend_stage_output_budget(
    stage: str,
    base_budget: int,
    *,
    effort: EffortDecision | None = None,
    disagreement_detected: bool = False,
) -> int:
    cap = max(256, int(base_budget or 0))
    token = str(stage or "").strip().lower()

    if token in {"minister_reasoning", "round2_reasoning"}:
        level = str(getattr(effort, "level", "medium") or "medium").lower()
        if level == "low":
            return min(cap, 1200)
        if level == "medium":
            return min(cap, 2400)
        return cap

    if token in {"red_team", "red_team_refine", "debate"}:
        if disagreement_detected:
            return cap
        return min(cap, 1000)

    if token == "final_synthesis":
        level = str(getattr(effort, "level", "medium") or "medium").lower()
        if level == "low":
            return min(cap, 2400)
        if level == "medium":
            return min(cap, 3000)
        return cap

    return cap


def stage_budget_instruction(
    stage: str,
    *,
    effort: EffortDecision | None = None,
    disagreement_detected: bool = False,
) -> str:
    token = str(stage or "").strip().lower()
    if token in {"minister_reasoning", "round2_reasoning"}:
        level = str(getattr(effort, "level", "medium") or "medium").lower()
        if level == "low":
            return "Keep reasoning short and focused. Use 120 words or fewer inside the rationale field."
        if level == "medium":
            return "Keep reasoning short and focused. Use 220 words or fewer inside the rationale field."
        return "Keep reasoning short and focused. Use 300 words or fewer inside the rationale field."
    if token in {"red_team", "red_team_refine", "debate"}:
        if disagreement_detected:
            return "Surface only the strongest conflicts. Prefer 3 sharp critique points over long explanation."
        return "There is limited disagreement. Return only the most critical challenge points and stop early."
    if token == "final_synthesis":
        return "Focus on decision clarity, not narrative expansion. Do not use the full token budget unless necessary."
    return "Be concise. Do not use the full token budget unnecessarily."


__all__ = [
    "EffortDecision",
    "decide_effort",
    "effort_metadata",
    "estimate_complexity",
    "estimate_uncertainty",
    "recommend_stage_output_budget",
    "stage_budget_instruction",
]
