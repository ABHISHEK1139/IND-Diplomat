"""
Minister Curriculum Planner — Per-Minister Targeted Improvement
================================================================

Autonomous_3.0 pattern: breaks big improvements into small testable units.
Each minister gets targeted tasks from replay performance data.

Port of DIP_8 concept with A3.0 curriculum planning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer4_Reasoning.curriculum")


@dataclass
class LearningTarget:
    """A small, testable improvement for a minister."""
    minister: str
    skill: str
    current_accuracy: float
    target_accuracy: float
    method: str
    success_test: str
    priority: float  # 0-1
    status: str = "planned"


class MinisterCurriculum:
    """Generates targeted improvement plans for each minister."""

    def __init__(self):
        self.targets: Dict[str, List[LearningTarget]] = {}

    def assess_from_replay(
        self,
        minister_name: str,
        accuracy: float,
        errors: List[Dict[str, Any]],
    ) -> List[LearningTarget]:
        """Generate learning targets from replay performance data.

        Args:
            minister_name: Minister being assessed
            accuracy: Current accuracy from replay
            errors: List of error details [{scenario, expected, actual, reason}]

        Returns:
            Ranked list of LearningTargets
        """
        targets: List[LearningTarget] = []

        # Domain-specific improvement areas
        if minister_name == "Security Minister" and accuracy < 0.7:
            targets.append(LearningTarget(
                minister=minister_name,
                skill="distinguish_mobilization_from_exercise",
                current_accuracy=accuracy,
                target_accuracy=0.8,
                method="Replay 50 historical mobilization vs exercise scenarios with feedback",
                success_test="Accuracy on mobilization classification > 0.80",
                priority=0.9,
            ))

        if minister_name == "Economic Minister" and accuracy < 0.65:
            targets.append(LearningTarget(
                minister=minister_name,
                skill="sanctions_impact_assessment",
                current_accuracy=accuracy,
                target_accuracy=0.75,
                method="Replay sanctions scenarios with World Bank economic baselines",
                success_test="Sanctions impact correlation > 0.75 with ground truth",
                priority=0.85,
            ))

        if minister_name == "Contrarian Minister" and accuracy < 0.5:
            targets.append(LearningTarget(
                minister=minister_name,
                skill="alternative_explanation_generation",
                current_accuracy=accuracy,
                target_accuracy=0.6,
                method="Generate 3 alternatives per scenario; score by discrimination power",
                success_test="At least 1 correct alternative identified in 60% of scenarios",
                priority=0.7,
            ))

        # Generic improvements
        if accuracy < 0.6:
            targets.append(LearningTarget(
                minister=minister_name,
                skill="confidence_calibration",
                current_accuracy=accuracy,
                target_accuracy=0.7,
                method="Calibrate using sklearn calibration_curve on replay data",
                success_test="Brier score < 0.15",
                priority=0.95,
            ))

        # Rank by priority
        targets.sort(key=lambda t: t.priority, reverse=True)
        self.targets[minister_name] = targets
        return targets

    def get_next_target(self, minister_name: str) -> Optional[LearningTarget]:
        """Get the highest-priority uncompleted target for a minister."""
        for t in self.targets.get(minister_name, []):
            if t.status == "planned":
                return t
        return None

    def mark_complete(self, minister_name: str, skill: str) -> None:
        """Mark a learning target as completed."""
        for t in self.targets.get(minister_name, []):
            if t.skill == skill:
                t.status = "completed"

    def get_all_targets(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all learning targets for all ministers."""
        return {
            minister: [
                {"skill": t.skill, "current": t.current_accuracy, "target": t.target_accuracy, "priority": t.priority, "status": t.status}
                for t in targets
            ]
            for minister, targets in self.targets.items()
        }


_curriculum: Optional[MinisterCurriculum] = None


def get_curriculum() -> MinisterCurriculum:
    global _curriculum
    if _curriculum is None:
        _curriculum = MinisterCurriculum()
    return _curriculum
