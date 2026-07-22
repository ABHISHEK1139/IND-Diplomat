"""Crisis replay benchmark utilities for DIP 2.0.

These benchmarks replay historical or synthetic scenarios and compare outputs
for stability, calibration, and minister consistency.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from dip.unified_pipeline import execute


@dataclass
class ReplayCase:
    """A single replay scenario."""
    name: str
    query: str
    country: str
    expected_threat_level: Optional[str] = None
    min_verification_score: float = 0.0


@dataclass
class ReplayResult:
    """Result of replaying a crisis case."""
    case_name: str
    status: str
    threat_level: Optional[str]
    verification_score: float
    elapsed_seconds: float
    passed: bool
    notes: List[str]


class CrisisReplayBenchmark:
    """Run assessment replays against a set of cases."""

    def __init__(self, cases: List[ReplayCase]):
        self.cases = cases

    async def run_case(self, case: ReplayCase) -> ReplayResult:
        result = await execute(case.query, case.country)
        threat = result.get("threat_level")
        verification = float(result.get("verification_score", 0.0))
        passed = True
        notes: List[str] = []

        if case.expected_threat_level and threat != case.expected_threat_level:
            passed = False
            notes.append(f"Expected {case.expected_threat_level}, got {threat}")
        if verification < case.min_verification_score:
            passed = False
            notes.append(f"Verification {verification:.2f} below {case.min_verification_score:.2f}")

        return ReplayResult(
            case_name=case.name,
            status=str(result.get("status", "UNKNOWN")),
            threat_level=threat,
            verification_score=verification,
            elapsed_seconds=float(result.get("elapsed_seconds", 0.0)),
            passed=passed,
            notes=notes,
        )

    async def run_all(self) -> List[ReplayResult]:
        results: List[ReplayResult] = []
        for case in self.cases:
            results.append(await self.run_case(case))
        return results

    @staticmethod
    def summarize(results: List[ReplayResult]) -> Dict[str, Any]:
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total else 0.0,
        }

    @staticmethod
    def export_results(results: List[ReplayResult], filepath: str) -> None:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in results], f, indent=2)
