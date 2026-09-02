"""
Phase 12: Ablation Study Framework.

Runs the pipeline with components selectively disabled to measure
which component actually improves forecasting.

Configurations:
  - FULL: All components enabled
  - NO_BAYESIAN: Bayesian state model disabled
  - NO_DEBATE: Multi-agent debate disabled (single-agent)
  - NO_CONTRARIAN: Red Team Contrarian disabled
  - NO_VERIFICATION: CoVe/CRAG verification disabled
  - NO_TEMPORAL: Temporal memory & belief revision disabled

Then compares Brier Score, Calibration, Precision, Recall across configurations.
"""

import logging
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from dip.pipeline.deliberation.reasoning.backtesting import (
    BacktestEngine,
    BacktestMetrics,
    ForecastResult,
    HistoricalCase,
    HISTORICAL_CASES,
)

logger = logging.getLogger("Layer7.Ablation")


class AblationConfig(str, Enum):
    FULL = "FULL"
    NO_BAYESIAN = "NO_BAYESIAN"
    NO_DEBATE = "NO_DEBATE"
    NO_CONTRARIAN = "NO_CONTRARIAN"
    NO_VERIFICATION = "NO_VERIFICATION"
    NO_TEMPORAL = "NO_TEMPORAL"


class AblationResult(BaseModel):
    config: str
    metrics: BacktestMetrics
    delta_brier: float = 0.0  # vs FULL system


class AblationStudy:
    """
    Runs the full backtest suite under multiple ablation configurations
    and compares the results to identify which components add value.
    """

    def __init__(self):
        self.results: Dict[str, AblationResult] = {}
        self.baseline_brier: Optional[float] = None

    def run_config(
        self,
        config: AblationConfig,
        forecast_results: List[ForecastResult],
        cases: Optional[List[HistoricalCase]] = None,
    ) -> AblationResult:
        """
        Run backtesting under a specific ablation configuration.
        The caller is responsible for producing forecast_results
        with the appropriate component disabled.
        """
        if cases is None:
            cases = HISTORICAL_CASES

        engine = BacktestEngine()
        for r in forecast_results:
            engine.add_result(r)

        metrics = engine.compute_metrics(cases)

        # Track baseline
        if config == AblationConfig.FULL:
            self.baseline_brier = metrics.brier_score

        delta = (
            metrics.brier_score - self.baseline_brier
            if self.baseline_brier is not None
            else 0.0
        )

        result = AblationResult(
            config=config.value,
            metrics=metrics,
            delta_brier=round(delta, 4),
        )

        self.results[config.value] = result

        logger.info(
            f"[Ablation] {config.value}: Brier={metrics.brier_score} "
            f"ΔBrier={delta:+.4f} Prec={metrics.precision} Rec={metrics.recall}"
        )

        return result

    def summary(self) -> Dict:
        """
        Returns a summary table showing which components help.
        Positive delta_brier = component HELPS (removing it makes things worse).
        Negative delta_brier = component HURTS (removing it makes things better).
        """
        rows = []
        for config_name, result in self.results.items():
            rows.append(
                {
                    "config": config_name,
                    "brier_score": result.metrics.brier_score,
                    "delta_brier": result.delta_brier,
                    "precision": result.metrics.precision,
                    "recall": result.metrics.recall,
                    "calibration_error": result.metrics.calibration_error,
                    "verdict": (
                        "BASELINE"
                        if config_name == "FULL"
                        else ("HELPS" if result.delta_brier > 0 else "NEUTRAL/HURTS")
                    ),
                }
            )

        return {
            "ablation_results": rows,
            "conclusion": self._generate_conclusion(),
        }

    def _generate_conclusion(self) -> str:
        """Generate a human-readable conclusion about component value."""
        if not self.results or "FULL" not in self.results:
            return "Insufficient data for conclusion."

        helpful = []
        neutral = []
        for config_name, result in self.results.items():
            if config_name == "FULL":
                continue
            component = config_name.replace("NO_", "")
            if result.delta_brier > 0.02:
                helpful.append((component, result.delta_brier))
            else:
                neutral.append((component, result.delta_brier))

        helpful.sort(key=lambda x: x[1], reverse=True)

        parts = []
        if helpful:
            parts.append(
                "Components that improve forecasting (removing them hurts): "
                + ", ".join(f"{c} (Δ={d:+.4f})" for c, d in helpful)
            )
        if neutral:
            parts.append(
                "Components with marginal/no impact: "
                + ", ".join(f"{c} (Δ={d:+.4f})" for c, d in neutral)
            )

        return ". ".join(parts) if parts else "All components appear equivalent."
