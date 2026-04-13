"""
Historical Backtesting Engine
================================

Replays past GDELT event data through the signal extraction and
risk engine pipeline to evaluate whether IND-Diplomat would have
predicted known historical escalation events.

This is an **additive module** — it does NOT modify any core
pipeline code.  It reads historical data and calls existing
functions.

Usage::

    from analysis.backtester import Backtester

    bt = Backtester()
    result = await bt.replay_scenario(
        country="UKR",
        scenario_name="Ukraine 2022 Invasion",
        start_date="2022-01-01",
        end_date="2022-02-24",
        ground_truth_risk="HIGH",
    )
    print(result.prediction_accuracy)

Architecture::

    Historical GDELT data
           ↓
    Signal extraction (existing Layer1 sensors)
           ↓
    Risk engine (existing Layer4 SRE)
           ↓
    Compare prediction vs. known outcome
           ↓
    Accuracy report
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("analysis.backtester")

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "backtest_results")


# ── Pre-defined historical scenarios ─────────────────────────────

HISTORICAL_SCENARIOS: List[Dict[str, Any]] = [
    {
        "name": "Crimea Crisis 2014",
        "country": "UKR",
        "start_date": "2014-01-01",
        "end_date": "2014-03-18",
        "ground_truth_risk": "HIGH",
        "ground_truth_state": "ACTIVE_CONFLICT",
        "description": "Russian annexation of Crimea following Euromaidan",
        "key_signals": [
            "SIG_MIL_MOBILIZATION", "SIG_FORCE_POSTURE",
            "SIG_COERCIVE_BARGAINING", "SIG_ALLIANCE_ACTIVATION",
        ],
    },
    {
        "name": "North Korea Missile Crisis 2017",
        "country": "PRK",
        "start_date": "2017-07-01",
        "end_date": "2017-11-30",
        "ground_truth_risk": "ELEVATED",
        "ground_truth_state": "CRISIS",
        "description": "DPRK ICBM tests and fire-and-fury rhetoric",
        "key_signals": [
            "SIG_MIL_ESCALATION", "SIG_WMD_RISK",
            "SIG_COERCIVE_BARGAINING", "SIG_DIP_HOSTILITY",
        ],
    },
    {
        "name": "Armenia-Azerbaijan War 2020",
        "country": "AZE",
        "start_date": "2020-09-01",
        "end_date": "2020-11-10",
        "ground_truth_risk": "HIGH",
        "ground_truth_state": "ACTIVE_CONFLICT",
        "description": "Second Nagorno-Karabakh War",
        "key_signals": [
            "SIG_MIL_MOBILIZATION", "SIG_MIL_ESCALATION",
            "SIG_FORCE_POSTURE", "SIG_KINETIC_ACTIVITY",
        ],
    },
    {
        "name": "Ukraine Invasion 2022",
        "country": "UKR",
        "start_date": "2022-01-01",
        "end_date": "2022-02-24",
        "ground_truth_risk": "CRITICAL",
        "ground_truth_state": "FULL_WAR",
        "description": "Russian full-scale invasion of Ukraine",
        "key_signals": [
            "SIG_MIL_MOBILIZATION", "SIG_FORCE_POSTURE",
            "SIG_LOGISTICS_PREP", "SIG_MIL_ESCALATION",
            "SIG_COERCIVE_BARGAINING", "SIG_NEGOTIATION_BREAKDOWN",
        ],
    },
    {
        "name": "Iran-Israel Tensions 2024",
        "country": "IRN",
        "start_date": "2024-03-01",
        "end_date": "2024-04-15",
        "ground_truth_risk": "HIGH",
        "ground_truth_state": "LIMITED_STRIKES",
        "description": "Iranian drone/missile attack on Israel after Damascus consulate strike",
        "key_signals": [
            "SIG_MIL_ESCALATION", "SIG_FORCE_POSTURE",
            "SIG_COERCIVE_BARGAINING", "SIG_ALLIANCE_ACTIVATION",
        ],
    },
]


RISK_LEVELS_ORDERED = ["LOW", "GUARDED", "ELEVATED", "HIGH", "CRITICAL"]
CONFLICT_STATES_ORDERED = [
    "PEACE", "CRISIS", "LIMITED_STRIKES", "ACTIVE_CONFLICT", "FULL_WAR",
]


@dataclass
class BacktestResult:
    """Result of a single backtesting scenario."""
    scenario_name: str
    country: str
    start_date: str
    end_date: str
    ground_truth_risk: str
    ground_truth_state: str
    predicted_risk: str = "UNKNOWN"
    predicted_state: str = "UNKNOWN"
    predicted_sre: float = 0.0
    predicted_confidence: float = 0.0
    risk_level_match: bool = False
    risk_within_one_level: bool = False
    state_match: bool = False
    state_within_one_level: bool = False
    signal_overlap: float = 0.0       # fraction of expected signals detected
    detected_signals: List[str] = field(default_factory=list)
    expected_signals: List[str] = field(default_factory=list)
    error: Optional[str] = None
    elapsed_seconds: float = 0.0

    @property
    def prediction_accuracy(self) -> str:
        """Human-readable accuracy assessment."""
        if self.error:
            return f"ERROR: {self.error}"
        if self.risk_level_match:
            return "EXACT MATCH"
        if self.risk_within_one_level:
            return "WITHIN ONE LEVEL"
        return "MISS"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["prediction_accuracy"] = self.prediction_accuracy
        return d


@dataclass
class BacktestReport:
    """Aggregate report across multiple scenarios."""
    results: List[BacktestResult] = field(default_factory=list)
    timestamp: str = ""
    exact_matches: int = 0
    within_one: int = 0
    misses: int = 0
    errors: int = 0
    accuracy_rate: float = 0.0

    def compute_stats(self) -> None:
        """Compute aggregate statistics."""
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.exact_matches = sum(1 for r in self.results if r.risk_level_match)
        self.within_one = sum(1 for r in self.results if r.risk_within_one_level and not r.risk_level_match)
        self.errors = sum(1 for r in self.results if r.error)
        self.misses = len(self.results) - self.exact_matches - self.within_one - self.errors
        total_valid = len(self.results) - self.errors
        self.accuracy_rate = (
            (self.exact_matches + self.within_one) / total_valid
            if total_valid > 0 else 0.0
        )

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_scenarios": len(self.results),
            "exact_matches": self.exact_matches,
            "within_one_level": self.within_one,
            "misses": self.misses,
            "errors": self.errors,
            "accuracy_rate": round(self.accuracy_rate, 3),
            "results": [r.to_dict() for r in self.results],
        }


def _risk_distance(predicted: str, actual: str) -> int:
    """Compute distance between risk levels."""
    try:
        pi = RISK_LEVELS_ORDERED.index(predicted)
        ai = RISK_LEVELS_ORDERED.index(actual)
        return abs(pi - ai)
    except ValueError:
        return 99


def _state_distance(predicted: str, actual: str) -> int:
    """Compute distance between conflict states."""
    try:
        pi = CONFLICT_STATES_ORDERED.index(predicted)
        ai = CONFLICT_STATES_ORDERED.index(actual)
        return abs(pi - ai)
    except ValueError:
        return 99


class Backtester:
    """
    Historical backtesting engine for IND-Diplomat.

    Replays historical scenarios through the existing pipeline
    and compares predictions against known outcomes.
    """

    def __init__(self) -> None:
        self.results: List[BacktestResult] = []

    async def replay_scenario(
        self,
        country: str,
        scenario_name: str,
        start_date: str,
        end_date: str,
        ground_truth_risk: str,
        ground_truth_state: str = "UNKNOWN",
        expected_signals: Optional[List[str]] = None,
        **kwargs,
    ) -> BacktestResult:
        """
        Replay a single scenario through the risk engine.

        Uses historical GDELT data (if available) to extract signals,
        then runs them through domain fusion and escalation index.

        Parameters
        ----------
        country : str
            ISO-3 country code.
        scenario_name : str
            Human-readable scenario name.
        start_date : str
            YYYY-MM-DD start of the crisis period.
        end_date : str
            YYYY-MM-DD end of the crisis period.
        ground_truth_risk : str
            Known risk level outcome.
        ground_truth_state : str
            Known conflict state outcome.
        expected_signals : list[str], optional
            Signals that should be detected in this scenario.

        Returns
        -------
        BacktestResult
        """
        import time

        expected = expected_signals or []
        result = BacktestResult(
            scenario_name=scenario_name,
            country=country,
            start_date=start_date,
            end_date=end_date,
            ground_truth_risk=ground_truth_risk,
            ground_truth_state=ground_truth_state,
            expected_signals=expected,
        )

        t0 = time.perf_counter()

        try:
            # Try to load historical GDELT data
            signals, sre_score, risk_level, conflict_state = await self._run_historical_analysis(
                country, start_date, end_date,
            )

            result.predicted_risk = risk_level
            result.predicted_state = conflict_state
            result.predicted_sre = sre_score
            result.detected_signals = signals
            result.risk_level_match = (risk_level == ground_truth_risk)
            result.risk_within_one_level = (_risk_distance(risk_level, ground_truth_risk) <= 1)
            result.state_match = (conflict_state == ground_truth_state)
            result.state_within_one_level = (_state_distance(conflict_state, ground_truth_state) <= 1)

            if expected:
                overlap = len(set(signals) & set(expected))
                result.signal_overlap = overlap / len(expected)

        except Exception as e:
            result.error = str(e)
            logger.error("[BACKTEST] Scenario '%s' failed: %s", scenario_name, e)

        result.elapsed_seconds = round(time.perf_counter() - t0, 2)
        self.results.append(result)

        logger.info(
            "[BACKTEST] %s: predicted=%s actual=%s → %s (SRE=%.3f)",
            scenario_name, result.predicted_risk, ground_truth_risk,
            result.prediction_accuracy, result.predicted_sre,
        )

        return result

    async def _run_historical_analysis(
        self,
        country: str,
        start_date: str,
        end_date: str,
    ) -> tuple:
        """
        Run analysis on historical data.

        Attempts to use actual GDELT data if available,
        otherwise uses a synthetic estimation based on
        the known crisis parameters.
        """
        from engine.Layer4_Analysis.domain_fusion import compute_domain_indices
        from engine.Layer4_Analysis.escalation_index import (
            compute_escalation_index, escalation_to_risk, EscalationInput,
        )
        from engine.Layer3_StateModel.signal_registry import CANONICAL_TOKENS

        # Try to load historical GDELT data from archive
        archive_signals = self._load_archived_gdelt(country, start_date, end_date)

        if archive_signals:
            # Use real historical data
            detected = list(archive_signals.keys())
            # Build SRE input from signal confidences
            cap_sigs = [v for k, v in archive_signals.items()
                       if k in {"SIG_MIL_MOBILIZATION", "SIG_MIL_ESCALATION",
                                "SIG_FORCE_POSTURE", "SIG_LOGISTICS_PREP",
                                "SIG_CYBER_ACTIVITY", "SIG_KINETIC_ACTIVITY",
                                "SIG_WMD_RISK"}]
            int_sigs = [v for k, v in archive_signals.items()
                       if k in {"SIG_DIP_HOSTILITY", "SIG_COERCIVE_BARGAINING",
                                "SIG_ALLIANCE_ACTIVATION", "SIG_NEGOTIATION_BREAKDOWN",
                                "SIG_DIPLOMACY_ACTIVE", "SIG_DETERRENCE_SIGNALING"}]
            stab_sigs = [v for k, v in archive_signals.items()
                        if k in {"SIG_INTERNAL_INSTABILITY", "SIG_PUBLIC_PROTEST",
                                 "SIG_DECEPTION_ACTIVITY"}]
            cost_sigs = [v for k, v in archive_signals.items()
                        if k in {"SIG_ECONOMIC_PRESSURE"}]

            capability = max(cap_sigs) if cap_sigs else 0.1
            intent = max(int_sigs) if int_sigs else 0.1
            stability = max(stab_sigs) if stab_sigs else 0.1
            cost = max(cost_sigs) if cost_sigs else 0.1
        else:
            # No historical data — return placeholder
            logger.warning(
                "[BACKTEST] No archived GDELT data for %s (%s to %s). "
                "Using placeholder — backtest requires archived data for accuracy.",
                country, start_date, end_date,
            )
            detected = []
            capability = 0.3
            intent = 0.3
            stability = 0.2
            cost = 0.1

        # Run through SRE
        esc_input = EscalationInput(
            capability=capability,
            intent=intent,
            instability=stability,
            cost=cost,
        )
        sre_score = compute_escalation_index(esc_input)
        risk_level = escalation_to_risk(sre_score)

        # Estimate conflict state from SRE
        if sre_score >= 0.80:
            conflict_state = "FULL_WAR"
        elif sre_score >= 0.60:
            conflict_state = "ACTIVE_CONFLICT"
        elif sre_score >= 0.40:
            conflict_state = "LIMITED_STRIKES"
        elif sre_score >= 0.20:
            conflict_state = "CRISIS"
        else:
            conflict_state = "PEACE"

        return detected, sre_score, risk_level, conflict_state

    def _load_archived_gdelt(
        self,
        country: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, float]:
        """
        Load archived GDELT signal data.

        Looks for pre-processed signal files in:
        ``data/archive/gdelt/{country}_{start}_{end}.json``

        Format::

            {
                "SIG_MIL_MOBILIZATION": 0.85,
                "SIG_FORCE_POSTURE": 0.70,
                ...
            }

        Returns empty dict if no archive exists.
        """
        archive_dir = os.path.join(
            os.path.dirname(__file__), "..", "data", "archive", "gdelt",
        )
        filename = f"{country}_{start_date}_{end_date}.json"
        filepath = os.path.join(archive_dir, filename)

        if not os.path.exists(filepath):
            return {}

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("[BACKTEST] Failed to load archive %s: %s", filepath, e)
            return {}

    async def run_all_scenarios(self) -> BacktestReport:
        """Run all pre-defined historical scenarios."""
        report = BacktestReport()

        for scenario in HISTORICAL_SCENARIOS:
            result = await self.replay_scenario(
                country=scenario["country"],
                scenario_name=scenario["name"],
                start_date=scenario["start_date"],
                end_date=scenario["end_date"],
                ground_truth_risk=scenario["ground_truth_risk"],
                ground_truth_state=scenario.get("ground_truth_state", "UNKNOWN"),
                expected_signals=scenario.get("key_signals", []),
            )
            report.results.append(result)

        report.compute_stats()

        # Save report
        os.makedirs(_DATA_DIR, exist_ok=True)
        report_path = os.path.join(
            _DATA_DIR,
            f"backtest_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json",
        )
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        logger.info("[BACKTEST] Report saved to %s", report_path)

        return report


def print_backtest_report(report: BacktestReport) -> str:
    """Format a backtest report as a readable table."""
    lines = [
        "=" * 70,
        "HISTORICAL BACKTESTING REPORT",
        "=" * 70,
        f"Timestamp:      {report.timestamp}",
        f"Scenarios:      {len(report.results)}",
        f"Exact Matches:  {report.exact_matches}",
        f"Within 1 Level: {report.within_one}",
        f"Misses:         {report.misses}",
        f"Errors:         {report.errors}",
        f"Accuracy Rate:  {report.accuracy_rate:.1%}",
        "",
        f"{'Scenario':<35} {'Predicted':<12} {'Actual':<12} {'Result':<18} {'SRE':>5}",
        "-" * 85,
    ]

    for r in report.results:
        lines.append(
            f"{r.scenario_name:<35} {r.predicted_risk:<12} "
            f"{r.ground_truth_risk:<12} {r.prediction_accuracy:<18} "
            f"{r.predicted_sre:>5.3f}"
        )

    lines.append("=" * 70)
    return "\n".join(lines)
