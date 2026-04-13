"""
Layer-4 question scope control.

Determines whether a question is within the system's analytical scope.

Scope categories
----------------
    risk_assessment          – risk/threat keywords present
    grounded_explanatory     – analytical framing (why / what factors / …)
    conditional_assessment   – analytical + predictive language combined
                              (e.g. "What factors will influence …")
    predictive_or_speculative – pure prediction with no analytical framing
    ambiguous                – cannot classify
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List
import re


# Patterns that *indicate* prediction / speculation.
BLOCKED_PATTERNS = [
    r"\bwho will win\b",
    r"\bpredict\b",
    r"\bforecast\b",
    r"\bprobability of\b",
    r"\bchance of\b",
    r"\bnext year\b",
    r"\bwill\b",         # generic – checked last; overridden by analytical framing
    r"\bin \d{4}\b",
    r"\bby \d{4}\b",
]

# Patterns that *indicate* analytical / explanatory framing.
ALLOWED_PATTERNS = [
    r"\bwhy\b",
    r"\bwhat factors\b",
    r"\bwhat legal justification\b",
    r"\bwhat signals\b",
    r"\bhow did\b",
    r"\bhow does\b",
    r"\bhow is\b",
    r"\bhow are\b",
    r"\bis .* increasing\b",
    r"\bwhat is driving\b",
    r"\bwhat are the\b",
    r"\bshould\b",
    r"\bcan\b",
    r"\banalyze\b",
    r"\bassess\b",
    r"\bassessment\b",
    r"\bevaluate\b",
    r"\bexplain\b",
    r"\bdescribe\b",
    r"\bidentify\b",
    r"\bmonitor\w*\b",
    r"\bestimate\b",
    r"\bposture\b",
    r"\bintelligence\b",
    r"\bcollection\b",
    r"\bgaps?\b",
]

# Negation prefixes that cancel a nearby blocked match.
# E.g. "not a forecast" or "do not predict" should not be blocked.
_NEGATION_PREFIX = re.compile(
    r"\b(?:not|no|don't|do\s+not|never|isn't|is\s+not|without)\s+(?:a\s+|an\s+)?",
    re.IGNORECASE,
)

RISK_KEYWORDS = [
    "threat", "risk", "danger", "security", "stability",
    "war", "escalation", "conflict", "tension", "crisis",
]


@dataclass
class ScopeCheckResult:
    allowed: bool
    scope: str
    reason: str
    blocked_matches: List[str] = field(default_factory=list)
    allowed_matches: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "allowed": self.allowed,
            "scope": self.scope,
            "reason": self.reason,
            "blocked_matches": self.blocked_matches,
            "allowed_matches": self.allowed_matches,
        }


def check_question_scope(question: str) -> ScopeCheckResult:
    text = str(question or "").strip()
    lowered = text.lower()
    if not lowered:
        return ScopeCheckResult(
            allowed=False,
            scope="unknown",
            reason="Question is empty.",
        )

    blocked = [p for p in BLOCKED_PATTERNS if re.search(p, lowered)]
    allowed = [p for p in ALLOWED_PATTERNS if re.search(p, lowered)]
    risk_hit = [k for k in RISK_KEYWORDS if k in lowered]

    # ── 0. Negation-aware filtering ───────────────────────────────────
    #    Drop blocked matches that appear only inside a negation context.
    #    E.g. "not a forecast" → \bforecast\b should be dropped.
    if blocked:
        surviving: list[str] = []
        for bp in blocked:
            m = re.search(bp, lowered)
            if m:
                prefix = lowered[max(0, m.start() - 30): m.start()]
                if _NEGATION_PREFIX.search(prefix):
                    continue           # negated → not a real prediction
            surviving.append(bp)
        blocked = surviving

    # Strong prediction words that should never be overridden by risk keywords
    _STRONG_PREDICT = {r"\bpredict\b", r"\bforecast\b", r"\bprobability of\b",
                       r"\bchance of\b", r"\bwho will win\b"}
    has_strong_predict = bool(set(blocked) & _STRONG_PREDICT)

    # ── 1. Risk keywords auto-allow — UNLESS strong prediction present ─
    if risk_hit and not has_strong_predict:
        return ScopeCheckResult(
            allowed=True,
            scope="risk_assessment",
            reason="Query is a structured Risk/Threat Assessment.",
            blocked_matches=blocked,
            allowed_matches=risk_hit + allowed,
        )

    # ── 2. Both blocked AND allowed patterns → conditional assessment ─
    #    "What factors will influence …" has both \bwhat factors\b and \bwill\b
    if blocked and allowed:
        return ScopeCheckResult(
            allowed=True,
            scope="conditional_assessment",
            reason=(
                "Question contains predictive language but is framed analytically. "
                "Proceeding as a conditional assessment."
            ),
            blocked_matches=blocked,
            allowed_matches=allowed,
        )

    # ── 3. Only blocked, no analytical framing → reject ───────────────
    if blocked:
        return ScopeCheckResult(
            allowed=False,
            scope="predictive_or_speculative",
            reason="Question requests prediction/speculation outside grounded analysis scope.",
            blocked_matches=blocked,
            allowed_matches=[],
        )

    # ── 4. Only allowed patterns → explanatory ────────────────────────
    if allowed:
        return ScopeCheckResult(
            allowed=True,
            scope="grounded_explanatory",
            reason="Question is explanatory and can be answered from current evidence.",
            blocked_matches=[],
            allowed_matches=allowed,
        )

    # ── 5. No patterns matched → ambiguous ────────────────────────────
    return ScopeCheckResult(
        allowed=False,
        scope="ambiguous",
        reason="Question is not clearly explanatory. Rephrase to ask about observed factors/signals.",
        blocked_matches=[],
        allowed_matches=[],
    )


def enforce_question_scope(question: str) -> None:
    report = check_question_scope(question)
    if report.allowed:
        return
    raise ValueError(report.reason)


__all__ = ["ScopeCheckResult", "check_question_scope", "enforce_question_scope"]

