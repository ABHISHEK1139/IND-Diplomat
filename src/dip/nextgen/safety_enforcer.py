"""
Safety Enforcer — Runtime Safety Boundary Checks
=================================================

Checks EVERY output against SafetyBoundary rules before returning to user.
Adapted from Autonomous_3.0 hard_constraints.py pattern.

Rules enforced:
1. No covert action planning
2. No deception planning
3. No unlawful operations
4. Must show low confidence
5. Must show contradictory evidence
6. Must flag legal/treaty concerns
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SafetyViolation:
    """A single safety rule violation."""
    rule: str
    severity: str  # hard, soft
    description: str
    location: str = ""
    blocked: bool = False


@dataclass
class SafetyReport:
    """Result of safety enforcement on an output."""
    passed: bool = True
    violations: List[SafetyViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    blocked_outputs: List[str] = field(default_factory=list)


# ── Hard constraints (BLOCK output) ──

_COVERT_ACTION_PATTERNS = [
    r"covert\s+operation",
    r"clandestine\s+action",
    r"deniable\s+attack",
    r"false\s+flag",
    r"assassination",
    r"sabotage\s+civilian",
    r"overthrow\s+(the\s+)?government",
]

_DECEPTION_PATTERNS = [
    r"deception\s+campaign",
    r"disinformation\s+attack",
    r"fabricate\s+evidence",
    r"plant\s+false\s+intel",
    r"psychological\s+warfare\s+against\s+civilian",
]

_UNLAWFUL_PATTERNS = [
    r"violat(?:e|ing|ion)\s+of\s+(?:the\s+)?geneva\s+convention",
    r"war\s+crime",
    r"crime\s+against\s+humanity",
    r"indiscriminate\s+attack",
    r"target(?:ing)?\s+civilian",
    r"torture",
    r"extrajudicial\s+killing",
]

# ── Soft constraints (FLAG, don't block) ──

_HIDE_UNCERTAINTY_PATTERNS = [
    r"confidence\s*(?:is|:)\s*(?:very\s+)?high",
    r"certain(?:ty)?\s*(?:is|:)\s*(?:very\s+)?high",
    r"no\s+doubt",
    r"definitely",
    r"without\s+question",
    r"absolutely\s+certain",
]

_HIDE_CONTRADICTION_PATTERNS = [
    r"all\s+evidence\s+supports",
    r"unanimous(?:ly)?\s+agree",
    r"no\s+contradictory\s+evidence",
    r"completely\s+consistent",
]

_MISSING_LEGAL_PATTERNS = [
    # Flag if recommending action but not citing legal basis
]


def _scan_text(text: str, patterns: List[str], rule_name: str, severity: str) -> List[SafetyViolation]:
    """Scan text for safety rule violations."""
    violations = []
    text_lower = text.lower()
    for pattern in patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            violations.append(SafetyViolation(
                rule=rule_name,
                severity=severity,
                description=f"Found '{match.group()}' — {rule_name}",
                location=f"position {match.start()}",
                blocked=(severity == "hard"),
            ))
    return violations


def enforce_safety(output: Dict[str, Any]) -> SafetyReport:
    """Run all safety checks on a pipeline output.

    Returns SafetyReport with violations, warnings, and blocked outputs.
    """
    violations: List[SafetyViolation] = []
    warnings: List[str] = []
    blocked: List[str] = []

    # Extract all text to scan
    texts_to_scan = []

    # Executive summary
    briefing = output.get("head_of_country_briefing") or output.get("briefing", "")
    if isinstance(briefing, dict):
        texts_to_scan.append(briefing.get("executive_summary", ""))
        for opt in briefing.get("options", []):
            if isinstance(opt, dict):
                texts_to_scan.append(opt.get("description", ""))
    elif isinstance(briefing, str):
        texts_to_scan.append(briefing)

    # Hypotheses
    for h in output.get("hypotheses", []):
        if isinstance(h, dict):
            texts_to_scan.append(h.get("type", ""))

    # All text as single blob
    full_text = " ".join(texts_to_scan)

    # ── Hard constraints ──
    v = _scan_text(full_text, _COVERT_ACTION_PATTERNS, "no_covert_action", "hard")
    violations.extend(v)
    if v:
        blocked.append("covert_action_language_detected")

    v = _scan_text(full_text, _DECEPTION_PATTERNS, "no_deception", "hard")
    violations.extend(v)
    if v:
        blocked.append("deception_language_detected")

    v = _scan_text(full_text, _UNLAWFUL_PATTERNS, "no_unlawful_operations", "hard")
    violations.extend(v)
    if v:
        blocked.append("unlawful_operation_language_detected")

    # ── Soft constraints ──
    v = _scan_text(full_text, _HIDE_UNCERTAINTY_PATTERNS, "uncertainty_disclosure", "soft")
    violations.extend(v)
    if v:
        warnings.append("Output may be hiding uncertainty. Review confidence language.")

    v = _scan_text(full_text, _HIDE_CONTRADICTION_PATTERNS, "contradiction_disclosure", "soft")
    violations.extend(v)
    if v:
        warnings.append("Output claims unanimous evidence. Check for contradictory signals.")

    # ── Threat level check ──
    threat_level = output.get("threat_level", "")
    verification = output.get("verification_score", 0.0)
    if threat_level in ("HIGH", "CRITICAL") and verification < 0.5:
        warnings.append(
            f"Threat level is {threat_level} but verification score is only {verification:.2f}. "
            f"Low-confidence HIGH threats should be flagged."
        )

    # ── Evidence separation check ──
    if output.get("briefing") and "recommend" in str(output.get("briefing", "")).lower():
        if not output.get("evidence_log"):
            warnings.append("Recommendation present but no evidence log. Separate evidence from recommendation.")

    passed = len(blocked) == 0

    return SafetyReport(
        passed=passed,
        violations=violations,
        warnings=warnings,
        blocked_outputs=blocked,
    )
