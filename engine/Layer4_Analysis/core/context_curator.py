from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from Config.config import (
    L4_CLASSIFICATION_INPUT_BUDGET,
    L4_CLASSIFICATION_OUTPUT_BUDGET,
    L4_MINISTER_INPUT_BUDGET,
    L4_MINISTER_OUTPUT_BUDGET,
    L4_REDTEAM_INPUT_BUDGET,
    L4_REDTEAM_OUTPUT_BUDGET,
    L4_SYNTHESIS_INPUT_BUDGET,
    L4_SYNTHESIS_OUTPUT_BUDGET,
)


ROLE_SIGNAL_HINTS: Dict[str, Tuple[str, ...]] = {
    "security": (
        "MIL", "FORCE", "LOGISTICS", "CYBER", "DETERRENCE", "KINETIC", "WMD",
    ),
    "diplomatic": (
        "DIP", "ALLIANCE", "NEGOTIATION", "COERCIVE", "RETALIATORY", "LEGAL", "DETERRENCE",
    ),
    "economic": (
        "ECO", "ECON", "TRADE", "SANCTIONS", "DEPENDENCY", "COST",
    ),
    "domestic": (
        "INTERNAL", "DOM", "UNREST", "STABILITY", "PROTEST", "REGIME",
    ),
    "contrarian": tuple(),
    "none": tuple(),
}


def estimate_tokens(text: Any) -> int:
    token = str(text or "").strip()
    if not token:
        return 0
    return max(1, (len(token) + 3) // 4)


def _clip_text(value: Any, limit: int) -> str:
    token = str(value or "").strip()
    if len(token) <= int(limit):
        return token
    return token[: max(0, int(limit) - 3)].rstrip() + "..."


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _role_key(minister_name: str | None) -> str:
    token = str(minister_name or "").strip().lower()
    if "security" in token or "military" in token:
        return "security"
    if "diplomatic" in token or "alliance" in token or "strategy" in token:
        return "diplomatic"
    if "economic" in token:
        return "economic"
    if "domestic" in token:
        return "domestic"
    if "contrarian" in token:
        return "contrarian"
    return "none"


def _recentness_bucket(raw_date: str) -> float:
    token = str(raw_date or "").strip()
    if not token:
        return 0.0
    try:
        normalized = token.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400.0)
    except Exception:
        return 0.0
    if age_days <= 14:
        return 1.0
    if age_days <= 45:
        return 0.8
    if age_days <= 90:
        return 0.55
    if age_days <= 180:
        return 0.35
    return 0.15


def _signal_rank(signal: str, confidence: float, role: str) -> Tuple[int, float]:
    hints = ROLE_SIGNAL_HINTS.get(role, ())
    upper = str(signal or "").upper()
    relevance = 1 if any(hint in upper for hint in hints) else 0
    if role == "contrarian":
        relevance = 1
    return (relevance, float(confidence))


def _top_signal_lines(signal_confidence: Dict[str, Any], role: str, limit: int = 10) -> List[str]:
    ranked: List[Tuple[Tuple[int, float], str, float]] = []
    for signal, confidence in dict(signal_confidence or {}).items():
        token = str(signal or "").strip().upper()
        if not token:
            continue
        conf = max(0.0, min(1.0, _safe_float(confidence)))
        ranked.append((_signal_rank(token, conf, role), token, conf))
    ranked.sort(key=lambda row: (-row[0][0], -row[0][1], row[1]))
    return [f"{signal}={conf:.3f}" for _, signal, conf in ranked[: max(1, int(limit))]]


def _state_snapshot_lines(state_context: Any, role: str) -> List[str]:
    military = getattr(state_context, "military", None)
    diplomatic = getattr(state_context, "diplomatic", None)
    economic = getattr(state_context, "economic", None)
    domestic = getattr(state_context, "domestic", None)
    pressures = getattr(state_context, "pressures", {}) or {}

    snapshots: Dict[str, List[str]] = {
        "security": [
            f"mobilization={_safe_float(getattr(military, 'mobilization_level', 0.0)):.3f}",
            f"clash_history={int(_safe_float(getattr(military, 'clash_history', 0)))}",
            f"exercises={int(_safe_float(getattr(military, 'exercises', 0)))}",
            f"capability_pressure={_safe_float(pressures.get('capability_pressure', 0.0)):.3f}",
        ],
        "diplomatic": [
            f"hostility={_safe_float(getattr(diplomatic, 'hostility_tone', 0.0)):.3f}",
            f"negotiations={_safe_float(getattr(diplomatic, 'negotiations', 0.0)):.3f}",
            f"alliances={_safe_float(getattr(diplomatic, 'alliances', 0.0)):.3f}",
            f"intent_pressure={_safe_float(pressures.get('intent_pressure', 0.0)):.3f}",
        ],
        "economic": [
            f"sanctions={_safe_float(getattr(economic, 'sanctions', 0.0)):.3f}",
            f"trade_dependency={_safe_float(getattr(economic, 'trade_dependency', 0.0)):.3f}",
            f"economic_pressure={_safe_float(getattr(economic, 'economic_pressure', 0.0)):.3f}",
            f"cost_index={_safe_float(getattr(state_context, 'cost_index', 0.0)):.3f}",
        ],
        "domestic": [
            f"regime_stability={_safe_float(getattr(domestic, 'regime_stability', 0.0)):.3f}",
            f"unrest={_safe_float(getattr(domestic, 'unrest', 0.0)):.3f}",
            f"protests={_safe_float(getattr(domestic, 'protests', 0.0)):.3f}",
            f"stability_pressure={_safe_float(pressures.get('stability_pressure', 0.0)):.3f}",
        ],
    }

    if role == "contrarian":
        merged: List[str] = []
        for group in snapshots.values():
            merged.extend(group[:2])
        return merged[:8]
    return snapshots.get(role, snapshots["security"][:2] + snapshots["diplomatic"][:2])


def _evidence_items_from_state(state_context: Any, signals: Sequence[str]) -> List[Tuple[float, str]]:
    evidence_items: List[Tuple[float, str]] = []
    signal_evidence = getattr(state_context, "signal_evidence", {}) or {}
    provenance_ctx = getattr(getattr(state_context, "evidence", None), "signal_provenance", {}) or {}

    def _append(signal: str, row: Any) -> None:
        payload = row if isinstance(row, dict) else getattr(row, "__dict__", {})
        source = _clip_text(payload.get("source") or payload.get("source_name") or "unknown", 48)
        date = str(payload.get("publication_date") or payload.get("date") or payload.get("timestamp") or "")
        excerpt = _clip_text(payload.get("excerpt") or payload.get("content") or payload.get("description") or "", 180)
        confidence = max(
            0.0,
            min(
                1.0,
                _safe_float(payload.get("confidence", payload.get("reliability", payload.get("score", 0.0)))),
            ),
        )
        freshness = _recentness_bucket(date)
        score = confidence + (freshness * 0.4)
        details = f"{signal} | src={source}"
        if date:
            details += f" | date={date}"
        if excerpt:
            details += f" | {excerpt}"
        evidence_items.append((score, details))

    seen_rows: set[Tuple[str, str, str]] = set()
    for signal in signals:
        token = str(signal or "").strip().upper()
        for payload_list in (
            list(signal_evidence.get(token, []) or []),
            list(provenance_ctx.get(token, []) or []),
        ):
            for row in payload_list:
                row_dict = row if isinstance(row, dict) else getattr(row, "__dict__", {})
                row_key = (
                    token,
                    str(row_dict.get("source") or row_dict.get("source_name") or ""),
                    str(row_dict.get("publication_date") or row_dict.get("date") or row_dict.get("timestamp") or ""),
                )
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)
                _append(token, row)
    evidence_items.sort(key=lambda item: -item[0])
    return evidence_items


@dataclass
class TaskProfile:
    task_type: str
    minister_role: str = "none"
    input_budget: int = 0
    output_budget: int = 0
    concise_instruction: str = ""
    drop_order: Tuple[str, ...] = (
        "prior_round_summary",
        "trajectory_block",
        "contradictions_block",
        "gaps_block",
        "evidence_block",
        "signal_block",
    )


@dataclass
class ContextPack:
    task_type: str
    minister_role: str
    question: str
    core_facts: str
    signal_block: str = ""
    evidence_block: str = ""
    gaps_block: str = ""
    contradictions_block: str = ""
    trajectory_block: str = ""
    prior_round_summary: str = ""
    task_instructions: str = ""
    output_schema: str = ""
    input_budget: int = 0
    output_budget: int = 0
    dropped_sections: List[str] = field(default_factory=list)
    pack_down_events: int = 0
    overflow: bool = False
    estimated_tokens: int = 0
    rendered_prompt: str = ""

    def render(self) -> str:
        sections: List[str] = []
        if self.task_instructions:
            sections.append(f"TASK:\n{self.task_instructions}")
        if self.question:
            sections.append(f"QUESTION:\n{self.question}")
        sections.append(f"CORE FACTS:\n{self.core_facts}")
        if self.signal_block:
            sections.append(f"SIGNALS:\n{self.signal_block}")
        if self.evidence_block:
            sections.append(f"EVIDENCE:\n{self.evidence_block}")
        if self.gaps_block:
            sections.append(f"GAPS:\n{self.gaps_block}")
        if self.contradictions_block:
            sections.append(f"CONTRADICTIONS:\n{self.contradictions_block}")
        if self.trajectory_block:
            sections.append(f"TRAJECTORY:\n{self.trajectory_block}")
        if self.prior_round_summary:
            sections.append(f"PRIOR ROUND:\n{self.prior_round_summary}")
        if self.output_schema:
            sections.append(f"OUTPUT CONTRACT:\n{self.output_schema}")
        self.rendered_prompt = "\n\n".join(section for section in sections if section.strip()).strip()
        self.estimated_tokens = estimate_tokens(self.rendered_prompt)
        return self.rendered_prompt


def task_profile(task_type: str, minister_role: str = "none") -> TaskProfile:
    token = str(task_type or "minister_reasoning").strip().lower()
    if token == "classification":
        return TaskProfile(
            task_type=token,
            minister_role=minister_role,
            input_budget=L4_CLASSIFICATION_INPUT_BUDGET,
            output_budget=L4_CLASSIFICATION_OUTPUT_BUDGET,
            concise_instruction=(
                "Use only the provided numeric state facts. Return compact JSON only. "
                "Complete required fields first and do not use the full token budget unnecessarily."
            ),
        )
    if token in {"red_team", "debate"}:
        return TaskProfile(
            task_type=token,
            minister_role=minister_role,
            input_budget=L4_REDTEAM_INPUT_BUDGET,
            output_budget=L4_REDTEAM_OUTPUT_BUDGET,
            concise_instruction=(
                "Be concise. Surface only critical attack paths or conflicts. "
                "Prefer sharp bullets over long explanation."
            ),
        )
    if token == "final_synthesis":
        return TaskProfile(
            task_type=token,
            minister_role=minister_role,
            input_budget=L4_SYNTHESIS_INPUT_BUDGET,
            output_budget=L4_SYNTHESIS_OUTPUT_BUDGET,
            concise_instruction=(
                "Produce only decision-relevant synthesis. Focus on decision clarity, not narrative expansion."
            ),
        )
    return TaskProfile(
        task_type=token,
        minister_role=minister_role,
        input_budget=L4_MINISTER_INPUT_BUDGET,
        output_budget=L4_MINISTER_OUTPUT_BUDGET,
        concise_instruction=(
            "Be concise. Focus only on decision-relevant evidence and reasoning. "
            "Keep any rationale inside the JSON field and under 150 words. "
            "Do not use the full token budget unnecessarily."
        ),
    )


def _apply_budget(pack: ContextPack, profile: TaskProfile) -> ContextPack:
    prompt = pack.render()
    if estimate_tokens(prompt) <= int(profile.input_budget):
        return pack

    shrink_plan: List[Tuple[str, Optional[int]]] = [
        ("evidence_block", 3),
        ("signal_block", 6),
        ("prior_round_summary", 280),
        ("trajectory_block", 180),
        ("contradictions_block", 200),
        ("gaps_block", 200),
        ("evidence_block", 0),
        ("prior_round_summary", 0),
        ("trajectory_block", 0),
        ("contradictions_block", 0),
        ("gaps_block", 0),
    ]

    for field_name, target in shrink_plan:
        current = str(getattr(pack, field_name, "") or "")
        if not current:
            continue
        pack.pack_down_events += 1
        if target == 0:
            setattr(pack, field_name, "")
            pack.dropped_sections.append(field_name)
        elif "\n" in current and field_name in {"evidence_block", "signal_block"}:
            lines = [line for line in current.splitlines() if line.strip()]
            setattr(pack, field_name, "\n".join(lines[: int(target)]))
        else:
            setattr(pack, field_name, _clip_text(current, int(target)))
        prompt = pack.render()
        if estimate_tokens(prompt) <= int(profile.input_budget):
            return pack

    pack.overflow = estimate_tokens(pack.render()) > int(profile.input_budget)
    return pack


def build_minister_classification_pack(
    *,
    minister_name: str,
    state_context: Any,
    specific_instructions: str,
    output_schema: str,
    question: str = "",
) -> ContextPack:
    role = _role_key(minister_name)
    profile = task_profile("classification", role)
    actors = getattr(state_context, "actors", None)
    subject = str(getattr(actors, "subject_country", "") or "unknown")
    target = str(getattr(actors, "target_country", "") or "unknown")
    signal_lines = _top_signal_lines(getattr(state_context, "signal_confidence", {}) or {}, role, limit=8)
    state_lines = _state_snapshot_lines(state_context, role)

    pack = ContextPack(
        task_type=profile.task_type,
        minister_role=role,
        question=question,
        core_facts=(
            f"minister={minister_name}\n"
            f"subject_country={subject}\n"
            f"target_country={target}\n"
            f"risk_level={str(getattr(state_context, 'risk_level', 'UNKNOWN') or 'UNKNOWN')}\n"
            f"observation_is_real={bool(getattr(getattr(state_context, 'observation_quality', None), 'is_observed', False))}"
        ),
        signal_block="\n".join(state_lines + signal_lines[:4]),
        evidence_block="",
        gaps_block="",
        contradictions_block="",
        trajectory_block="",
        prior_round_summary="",
        task_instructions=f"{specific_instructions}\n{profile.concise_instruction}".strip(),
        output_schema=output_schema,
        input_budget=profile.input_budget,
        output_budget=profile.output_budget,
    )
    return _apply_budget(pack, profile)


def build_minister_reasoning_pack(
    *,
    minister_name: str,
    session: Any,
    full_context: Any,
    report: Any,
    synthesis_summary: str = "",
    output_schema: str = "",
) -> ContextPack:
    role = _role_key(minister_name)
    task_name = "round2_reasoning" if synthesis_summary else "minister_reasoning"
    profile = task_profile(task_name, role)
    state_context = getattr(session, "state_context", None)
    question = str(getattr(session, "question", "") or "")
    actors = getattr(state_context, "actors", None)
    subject = str(getattr(actors, "subject_country", "") or "unknown")
    target = str(getattr(actors, "target_country", "") or "unknown")
    signal_confidence = dict(getattr(state_context, "signal_confidence", {}) or {})
    signal_lines = _top_signal_lines(signal_confidence, role, limit=10)
    evidence_rows = _evidence_items_from_state(state_context, [line.split("=")[0] for line in signal_lines])
    evidence_block = "\n".join(text for _, text in evidence_rows[:4])
    gaps = list(getattr(full_context, "gaps", []) or []) or list(getattr(getattr(session, "gap_report", None), "gaps", []) or [])
    contradictions = list(getattr(full_context, "contradictions", []) or []) or list(getattr(session, "identified_conflicts", []) or [])
    trajectory = getattr(full_context, "trajectory", {}) or {}
    trajectory_lines = [
        f"{key}={trajectory[key]}"
        for key in ("prob_up", "prob_down", "prob_stable", "velocity", "pre_war_warning")
        if key in trajectory
    ]

    pack = ContextPack(
        task_type=profile.task_type,
        minister_role=role,
        question=question,
        core_facts=(
            f"minister={minister_name}\n"
            f"subject_country={subject}\n"
            f"target_country={target}\n"
            f"current_predicted_signals={', '.join(list(getattr(report, 'predicted_signals', []) or [])[:6]) or 'NONE'}\n"
            f"escalation_score={_safe_float(getattr(full_context, 'escalation_score', 0.0)):.3f}\n"
            f"risk_level={str(getattr(state_context, 'risk_level', 'UNKNOWN') or 'UNKNOWN')}"
        ),
        signal_block="\n".join(signal_lines),
        evidence_block=evidence_block,
        gaps_block="\n".join(_clip_text(item, 180) for item in gaps[:4]),
        contradictions_block="\n".join(_clip_text(item, 180) for item in contradictions[:4]),
        trajectory_block="\n".join(trajectory_lines),
        prior_round_summary=_clip_text(synthesis_summary, 480),
        task_instructions=profile.concise_instruction,
        output_schema=output_schema,
        input_budget=profile.input_budget,
        output_budget=profile.output_budget,
    )
    return _apply_budget(pack, profile)


def build_red_team_query_pack(
    *,
    draft_answer: str,
    state_context: Dict[str, Any],
    minister_context: str = "",
    question: str = "",
    output_schema: str = "",
) -> ContextPack:
    profile = task_profile("red_team", "contrarian")
    signal_conf = dict((state_context or {}).get("signal_confidence", {}) or {})
    signal_lines = _top_signal_lines(signal_conf, "contrarian", limit=8)

    evidence_items: List[str] = []
    signal_sources = dict((state_context or {}).get("signal_sources", {}) or {})
    for signal, sources in list(signal_sources.items())[:5]:
        joined = ", ".join(sorted({str(src) for src in list(sources or [])[:3]}))
        if joined:
            evidence_items.append(f"{signal}: {joined}")

    pack = ContextPack(
        task_type=profile.task_type,
        minister_role="contrarian",
        question=question,
        core_facts=(
            f"draft_answer={_clip_text(draft_answer, 420)}\n"
            f"data_confidence={_safe_float(((state_context or {}).get('meta', {}) or {}).get('data_confidence', 0.0)):.3f}\n"
            f"source_count={int(_safe_float(((state_context or {}).get('meta', {}) or {}).get('source_count', 0)))}"
        ),
        signal_block="\n".join(signal_lines),
        evidence_block="\n".join(evidence_items[:4]),
        gaps_block="",
        contradictions_block=_clip_text(minister_context, 420),
        trajectory_block="",
        prior_round_summary="",
        task_instructions=profile.concise_instruction,
        output_schema=output_schema,
        input_budget=profile.input_budget,
        output_budget=profile.output_budget,
    )
    return _apply_budget(pack, profile)


def build_red_team_refinement_pack(
    *,
    draft_answer: str,
    critique: str,
    evidence: Sequence[str],
    question: str = "",
) -> ContextPack:
    profile = task_profile("red_team", "contrarian")
    pack = ContextPack(
        task_type="red_team_refine",
        minister_role="contrarian",
        question=question,
        core_facts=f"draft_answer={_clip_text(draft_answer, 520)}",
        signal_block="",
        evidence_block="\n".join(_clip_text(item, 180) for item in list(evidence or [])[:4]),
        gaps_block="",
        contradictions_block=_clip_text(critique, 420),
        trajectory_block="",
        prior_round_summary="",
        task_instructions="Revise only to address the critique. Keep the answer concise and balanced.",
        output_schema="Return only the revised answer text.",
        input_budget=profile.input_budget,
        output_budget=profile.output_budget,
    )
    return _apply_budget(pack, profile)


__all__ = [
    "ContextPack",
    "TaskProfile",
    "build_minister_classification_pack",
    "build_minister_reasoning_pack",
    "build_red_team_query_pack",
    "build_red_team_refinement_pack",
    "estimate_tokens",
    "task_profile",
]
