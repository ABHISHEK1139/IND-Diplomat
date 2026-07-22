from dip.Config.config import config
"""
Red Team — adversarial challenge for low-confidence or conflicting hypotheses.

When the council has conflicts or low-confidence hypotheses, the Red Team
finds contradictions and generates counter-arguments. All reads and
writes go through CouncilSession.

When FORCE_MINISTER_HEURISTIC=1: uses deterministic bias/contradiction
detection — NO LLM calls, NO document access.
"""

import json
from typing import List

try:
    import litellm
except ImportError:
    litellm = None

from dip.layer4_reasoning.council_session import CouncilSession
from dip.core.json_utils import strip_markdown_json

LLM_MODEL = config.LLM_MODEL

# Hypotheses below this confidence are automatically challenged
LOW_CONFIDENCE_THRESHOLD = 0.4


async def challenge(session: CouncilSession) -> CouncilSession:
    """
    Challenge the council's hypotheses by finding contradictions.

    The red team examines:
      - Hypotheses with low confidence (below threshold).
      - Pairs of hypotheses that conflict with each other.

    Findings are written to session.red_team_report.
    """
    targets = _select_targets(session)

    if not targets:
        session.red_team_report = ["No hypotheses require adversarial review."]
        return session

    # Deterministic heuristic mode
    if config.FORCE_MINISTER_HEURISTIC or litellm is None:
        session.red_team_report = _heuristic_challenge(targets, session)
        return session

    # LLM mode with fallback
    try:
        session.red_team_report = await _llm_challenge(targets, session)
    except Exception:
        session.red_team_report = _heuristic_challenge(targets, session)

    return session


def _heuristic_challenge(targets: List[dict], session: CouncilSession) -> List[str]:
    """
    Deterministic red team — NO LLM, NO document access.
    
    Detects biases and contradictions from hypothesis structure alone.
    """
    challenges: List[str] = []
    
    # Known cognitive bias patterns
    bias_patterns = {
        "military_escalation": "CONFIRMATION BIAS: Military-focused ministers may over-weight troop movements as escalation signals while ignoring diplomatic de-escalation.",
        "diplomatic_breakdown": "MIRROR IMAGING: Assuming adversary decision-making mirrors own cultural/strategic norms.",
        "economic_coercion": "ANCHORING BIAS: Over-weighting recent economic data while ignoring long-term trend reversals.",
        "strategic_assessment": "OVERCONFIDENCE: High-confidence strategic assessments often fail to account for adversary deception.",
        "domestic_instability": "AVAILABILITY BIAS: Recent protest imagery may inflate perceived instability relative to baseline.",
        "alliance_dynamics": "GROUPTHINK: Alliance cohesion assessments often underestimate free-rider problems.",
        "alternative_explanation": "FALSE UNIQUENESS: Assuming current crisis is unprecedented when historical patterns exist.",
    }
    
    for t in targets:
        reason = t.get("reason", "")
        htype = t.get("hypothesis_type", "")
        
        if reason == "low_confidence":
            minister = t.get("minister", "Unknown")
            conf = t.get("confidence", 0)
            challenges.append(
                f"LOW CONFIDENCE ({conf:.0%}): {minister}'s {htype} assessment "
                f"lacks evidence. Missing: {', '.join(t.get('missing_signals', [])[:3]) or 'all signals'}."
            )
            # Add bias warning if applicable
            for pattern_key, warning in bias_patterns.items():
                if pattern_key in htype.lower():
                    challenges.append(f"  ↳ {warning}")
                    break
        
        elif reason == "conflict":
            desc = t.get("description", "")
            challenges.append(f"CONFLICT DETECTED: {desc}")
    
    # Cross-check for contradictory confidence patterns
    confs = [h.confidence for h in session.hypotheses]
    if len(confs) >= 2 and max(confs) - min(confs) > 0.5:
        high_minister = max(session.hypotheses, key=lambda h: h.confidence).minister
        low_minister = min(session.hypotheses, key=lambda h: h.confidence).minister
        challenges.append(
            f"POLARIZATION: {high_minister} ({max(confs):.0%}) vs {low_minister} "
            f"({min(confs):.0%}) — confidence gap >50% suggests incomplete information sharing."
        )
    
    # Check for all-minister agreement (possible groupthink)
    if len(session.hypotheses) >= 3 and all(h.confidence > 0.7 for h in session.hypotheses):
        challenges.append(
            "GROUPTHINK WARNING: All ministers show >70% confidence — "
            "possible echo chamber. Consider alternative explanations."
        )
    
    return challenges if challenges else ["No structural biases detected in heuristic review."]


async def _llm_challenge(targets: List[dict], session: CouncilSession) -> List[str]:
    """LLM-based red team challenge (only when FORCE_MINISTER_HEURISTIC is off)."""
    targets_json = json.dumps(targets, indent=2)
    context_summary = (
        f"Country: {session.state_context.country}\n"
        f"Active conflicts: {', '.join(session.state_context.active_conflicts) or '(none)'}\n"
        f"Number of signals: {len(session.state_context.current_signals)}\n"
    )

    prompt = (
        "You are an adversarial red-team analyst. Your job is to find "
        "contradictions, logical gaps, and alternative explanations that "
        "the council may have missed.\n\n"
        f"Context:\n{context_summary}\n"
        f"Targets for challenge:\n{targets_json}\n\n"
        "For each target, produce a concise challenge statement that identifies:\n"
        "1. A specific alternative explanation.\n"
        "2. Potential Cognitive Biases (e.g. Mirror Imaging, Confirmation Bias).\n"
        "3. Failure Modes (e.g. False Positive, Deception/Decoy operations).\n"
        "Return a JSON array of challenge strings."
    )

    response = await litellm.acompletion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000
    )

    raw = response.choices[0].message.content.strip()
    try:
        raw = strip_markdown_json(raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(c) for c in parsed]
        elif isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return [str(c) for c in v]
        return [raw]
    except json.JSONDecodeError:
        return [f"Red team raw response (unparseable): {raw}"]


def _select_targets(session: CouncilSession) -> List[dict]:
    """Identify hypotheses that need adversarial scrutiny."""
    targets: List[dict] = []

    for h in session.hypotheses:
        if h.confidence < LOW_CONFIDENCE_THRESHOLD:
            targets.append({
                "reason": "low_confidence",
                "minister": h.minister,
                "hypothesis_type": h.hypothesis_type,
                "confidence": h.confidence,
                "predicted_signals": h.predicted_signals,
                "matched_signals": h.matched_signals,
                "missing_signals": h.missing_signals,
            })

    # Include any conflicts detected by the coordinator
    for conflict_desc in session.conflicts:
        targets.append({
            "reason": "conflict",
            "description": conflict_desc,
        })

    return targets


async def _generate_challenges(
    targets: List[dict], session: CouncilSession
) -> List[str]:
    """Ask the LLM to find contradictions and generate counter-arguments."""
    targets_json = json.dumps(targets, indent=2)
    context_summary = (
        f"Country: {session.state_context.country}\n"
        f"Active conflicts: {', '.join(session.state_context.active_conflicts) or '(none)'}\n"
        f"Number of signals: {len(session.state_context.current_signals)}\n"
    )

    prompt = (
        "You are an adversarial red-team analyst. Your job is to find "
        "contradictions, logical gaps, and alternative explanations that "
        "the council may have missed.\n\n"
        f"Context:\n{context_summary}\n"
        f"Targets for challenge:\n{targets_json}\n\n"
        "For each target, produce a concise challenge statement that identifies:\n"
        "1. A specific alternative explanation (e.g. seasonal training exercise, election rhetoric).\n"
        "2. Potential Cognitive Biases (e.g. Mirror Imaging, Confirmation Bias).\n"
        "3. Failure Modes (e.g. False Positive, Deception/Decoy operations).\n"
        "Return a JSON array of challenge strings."
    )

    response = await litellm.acompletion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000
    )

    raw = response.choices[0].message.content.strip()

    try:
        raw = strip_markdown_json(raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(c) for c in parsed]
        elif isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return [str(c) for c in v]
        return [raw]
    except json.JSONDecodeError:
        return [f"Red team raw response (unparseable): {raw}"]
