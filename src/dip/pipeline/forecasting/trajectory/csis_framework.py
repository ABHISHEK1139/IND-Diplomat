"""
CSIS Framework — Intelligence Methodology Wrappers
====================================================

Implements CSIS-grade analytical methodologies:
- ACH: Analysis of Competing Hypotheses
- Red Team: Structured adversarial challenge
- Scenario Planning: Multi-branch future analysis
- Devil's Advocacy: Argument from opposite position

Port of DIP_8 engine/Layer5_Judgment/csis_framework.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CSISMethod(str, Enum):
    ACH = "analysis_of_competing_hypotheses"
    RED_TEAM = "red_team"
    SCENARIO_PLANNING = "scenario_planning"
    DEVILS_ADVOCACY = "devils_advocacy"


@dataclass
class HypothesisEvidence:
    """How evidence relates to a hypothesis."""
    hypothesis: str
    consistent: List[str] = field(default_factory=list)
    inconsistent: List[str] = field(default_factory=list)
    neutral: List[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class ACHResult:
    """Output of Analysis of Competing Hypotheses."""
    hypotheses: List[HypothesisEvidence] = field(default_factory=list)
    most_likely: str = ""
    most_likely_score: float = 0.0
    discriminators: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ScenarioBranch:
    """One future scenario branch."""
    name: str
    probability: float = 0.0
    triggers: List[str] = field(default_factory=list)
    outcome: str = ""
    second_order_effects: List[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    """Output of scenario planning."""
    branches: List[ScenarioBranch] = field(default_factory=list)
    baseline: str = ""
    pessimistic: str = ""
    optimistic: str = ""
    black_swan: str = ""


def run_ach(
    hypotheses: List[str],
    evidence: List[str],
    scores: Optional[Dict[str, Dict[str, float]]] = None,
) -> ACHResult:
    """Run Analysis of Competing Hypotheses.

    For each hypothesis, classify evidence as consistent/inconsistent/neutral.
    Score by: (consistent - inconsistent) / total.
    Identify discriminators: evidence that strongly favors one hypothesis.
    """
    if not hypotheses:
        return ACHResult()

    results: List[HypothesisEvidence] = []
    for h in hypotheses:
        if scores and h in scores:
            evidence_scores = scores[h]
            consistent = [e for e in evidence if evidence_scores.get(e, 0) > 0.3]
            inconsistent = [e for e in evidence if evidence_scores.get(e, 0) < -0.3]
            neutral = [e for e in evidence if -0.3 <= evidence_scores.get(e, 0) <= 0.3]
            raw_score = sum(evidence_scores.get(e, 0) for e in evidence)
            score = max(0.0, min(1.0, (raw_score + len(evidence)) / (2 * len(evidence))))
        else:
            consistent = []
            inconsistent = []
            neutral = list(evidence)
            score = 1.0 / len(hypotheses) if hypotheses else 0.0

        results.append(HypothesisEvidence(
            hypothesis=h,
            consistent=consistent,
            inconsistent=inconsistent,
            neutral=neutral,
            score=round(score, 4),
        ))

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)
    best = results[0]

    # Find discriminators: evidence that appears in best's consistent AND in others' inconsistent
    discriminators: List[str] = []
    for e in best.consistent:
        for other in results[1:]:
            if e in other.inconsistent and e not in discriminators:
                discriminators.append(e)

    return ACHResult(
        hypotheses=results,
        most_likely=best.hypothesis,
        most_likely_score=best.score,
        discriminators=discriminators,
        recommendations=[f"Collect more evidence on: {d}" for d in discriminators[:3]],
    )


def run_red_team(
    conclusion: str,
    supporting_evidence: List[str],
    confidence: float,
) -> Dict[str, Any]:
    """Run structured red team challenge.

    Returns challenges organized by type:
    - evidence_gaps: missing evidence that would weaken the case
    - alternative_explanations: other ways to interpret the same evidence
    - mirror_imaging: assumptions that may reflect our bias, not theirs
    - worst_case: what happens if we're wrong
    """
    challenges: Dict[str, List[str]] = {
        "evidence_gaps": [],
        "alternative_explanations": [],
        "mirror_imaging": [],
        "worst_case": [],
    }

    if confidence > 0.8:
        challenges["evidence_gaps"].append(
            f"High confidence ({confidence:.0%}) may indicate confirmation bias. "
            f"What evidence would DISPROVE '{conclusion}'?"
        )

    if len(supporting_evidence) < 3:
        challenges["evidence_gaps"].append(
            f"Only {len(supporting_evidence)} pieces of supporting evidence. "
            f"Need at least 3 independent sources."
        )

    challenges["alternative_explanations"].append(
        f"What if the observed signals are domestic posturing, not external threat?"
    )
    challenges["alternative_explanations"].append(
        f"What if a third party is manipulating the information environment?"
    )

    challenges["mirror_imaging"].append(
        f"Are we assuming the adversary shares our risk calculus? "
        f"Their priorities may differ."
    )

    challenges["worst_case"].append(
        f"If '{conclusion}' is wrong, the policy response would be misaligned "
        f"with actual conditions, potentially escalating the situation."
    )

    return challenges


def run_devils_advocacy(
    conclusion: str,
    confidence: float,
) -> Dict[str, str]:
    """Generate the strongest possible argument AGAINST the current conclusion."""
    arguments: Dict[str, str] = {}

    arguments["counter_narrative"] = (
        f"The conclusion '{conclusion}' (confidence: {confidence:.0%}) "
        f"may be premature. Consider: the observed signals could be explained "
        f"by routine exercises, domestic political messaging, or third-party "
        f"disinformation rather than genuine hostile intent."
    )

    arguments["missing_evidence"] = (
        f"The assessment lacks independent corroboration from HUMINT sources "
        f"and relies primarily on OSINT/SIGINT. Without human-source confirmation, "
        f"the intent assessment is speculative."
    )

    arguments["base_rate"] = (
        f"Historically, similar signal patterns have resulted in escalation "
        f"only ~15% of the time. The base rate favors de-escalation."
    )

    return arguments


def run_scenario_planning(
    baseline: str,
    triggers: List[str],
    horizon_days: int = 30,
) -> ScenarioResult:
    """Generate multi-branch scenario analysis."""
    branches = [
        ScenarioBranch(
            name="Baseline",
            probability=0.45,
            triggers=triggers[:2] if triggers else [],
            outcome=f"{baseline} continues along current trajectory.",
            second_order_effects=[
                "Alliance relationships remain stable.",
                "Economic activity continues at current levels.",
            ],
        ),
        ScenarioBranch(
            name="Pessimistic",
            probability=0.25,
            triggers=triggers if triggers else [],
            outcome=f"Escalation within {horizon_days} days: {baseline} worsens significantly.",
            second_order_effects=[
                "Alliance activation and military posturing increase.",
                "Economic sanctions and trade disruption escalate.",
                "Diplomatic channels narrow or close.",
            ],
        ),
        ScenarioBranch(
            name="Optimistic",
            probability=0.20,
            triggers=["diplomatic_opening", "de-escalation_signal"],
            outcome=f"De-escalation within {horizon_days} days: {baseline} improves.",
            second_order_effects=[
                "Diplomatic channels reopen.",
                "Mutual de-escalation signals observed.",
                "Economic confidence returns.",
            ],
        ),
        ScenarioBranch(
            name="Black Swan",
            probability=0.10,
            triggers=["unexpected_external_shock", "leadership_change", "natural_disaster"],
            outcome=f"Unexpected discontinuity disrupts {baseline} trajectory.",
            second_order_effects=[
                "All previous assessments invalidated.",
                "Rapid policy adaptation required.",
                "Second and third-order effects unpredictable.",
            ],
        ),
    ]

    return ScenarioResult(
        branches=branches,
        baseline=branches[0].name,
        pessimistic=branches[1].name,
        optimistic=branches[2].name,
        black_swan=branches[3].name,
    )
