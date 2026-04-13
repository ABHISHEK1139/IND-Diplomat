from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence


def _estimate_tokens(text: Any) -> int:
    token = str(text or "").strip()
    if not token:
        return 0
    return max(1, (len(token) + 3) // 4)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _collect_reasoning_items(structured: Dict[str, Any], predicted_signals: Sequence[str] | None) -> List[str]:
    items: List[str] = []
    for key in ("primary_drivers", "critical_gaps", "counterarguments", "signals"):
        raw = structured.get(key, [])
        if isinstance(raw, str):
            raw = [raw]
        if isinstance(raw, Iterable):
            for item in raw:
                token = str(item or "").strip()
                if token:
                    items.append(token)
    for signal in list(predicted_signals or []):
        token = str(signal or "").strip()
        if token:
            items.append(token)
    deduped: List[str] = []
    seen = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


@dataclass(frozen=True)
class ReasoningAnalysis:
    overthinking: bool
    underthinking: bool
    signal_density: float
    length_ratio: float
    quality_score: float
    word_count: int
    token_estimate: int
    reasoning_item_count: int
    should_retry: bool
    issues: List[str]


def analyze_output(
    *,
    output_text: str,
    structured: Dict[str, Any],
    max_tokens: int,
    predicted_signals: Sequence[str] | None = None,
    confidence: float | None = None,
) -> ReasoningAnalysis:
    text = str(output_text or "").strip()
    words = len([part for part in text.split() if part.strip()])
    token_estimate = _estimate_tokens(text)
    reasoning_items = _collect_reasoning_items(structured or {}, predicted_signals)
    item_count = len(reasoning_items)
    signal_density = item_count / max(words, 1)
    length_ratio = token_estimate / max(int(max_tokens or 1), 1)
    confidence_value = max(
        0.0,
        min(
            1.0,
            _safe_float(
                confidence,
                _safe_float(
                    structured.get("justification_strength", structured.get("confidence", 0.5)),
                    0.5,
                ),
            ),
        ),
    )

    repetitive = False
    if words >= 80:
        unique_words = {part.lower() for part in text.split() if part.strip()}
        repetitive = (len(unique_words) / max(words, 1)) < 0.38

    overthinking = bool(
        (length_ratio > 0.90 and signal_density < 0.025)
        or (length_ratio > 0.82 and repetitive and signal_density < 0.03)
    )
    underthinking = bool(
        ((words < 90) and (item_count < 3 or confidence_value < 0.50 or signal_density < 0.02))
        or item_count < 2
        or confidence_value < 0.40
        or (signal_density < 0.012 and words < 160)
    )

    density_score = min(1.0, signal_density / 0.03)
    length_score = max(0.0, 1.0 - abs(length_ratio - 0.65))
    quality_score = max(
        0.0,
        min(
            1.0,
            (0.5 * density_score) + (0.3 * confidence_value) + (0.2 * length_score),
        ),
    )

    issues: List[str] = []
    if overthinking:
        issues.append("overthinking_detected")
    if underthinking:
        issues.append("underthinking_detected")
    if signal_density < 0.02:
        issues.append("low_signal_density")
    if item_count < 2:
        issues.append("too_few_reasoning_items")
    if confidence_value < 0.40:
        issues.append("weak_justification_strength")

    return ReasoningAnalysis(
        overthinking=overthinking,
        underthinking=underthinking,
        signal_density=round(signal_density, 4),
        length_ratio=round(length_ratio, 4),
        quality_score=round(quality_score, 4),
        word_count=words,
        token_estimate=token_estimate,
        reasoning_item_count=item_count,
        should_retry=bool(overthinking or underthinking),
        issues=issues,
    )


def build_adjustment_feedback(analysis: ReasoningAnalysis) -> str:
    if analysis.overthinking and not analysis.underthinking:
        return (
            "Reasoning monitor: the answer is overlong for its intelligence density. "
            "Keep the same structured conclusion, condense to only critical insights, "
            "avoid repetition, and keep rationale under 150 words."
        )
    if analysis.underthinking and not analysis.overthinking:
        return (
            "Reasoning monitor: the answer is too thin. Expand only the missing substance, "
            "add concrete drivers, gaps, or counterarguments as needed, and keep rationale under 220 words."
        )
    return (
        "Reasoning monitor: improve signal density and completeness without rewriting everything. "
        "Keep the structured answer intact and revise only the weak parts."
    )


def recommend_adjusted_budget(
    current_budget: int,
    *,
    hard_cap: int,
    analysis: ReasoningAnalysis,
) -> int:
    base = max(256, int(current_budget or 0))
    cap = max(base, int(hard_cap or base))
    if analysis.overthinking and not analysis.underthinking:
        return max(256, min(cap, int(base * 0.8)))
    if analysis.underthinking and not analysis.overthinking:
        return max(256, min(cap, int(base * 1.2)))
    return max(256, min(cap, base))


__all__ = [
    "ReasoningAnalysis",
    "analyze_output",
    "build_adjustment_feedback",
    "recommend_adjusted_budget",
]
