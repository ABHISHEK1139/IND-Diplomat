"""
Calibration Metrics — DIP 2.1 Validation Suite

Quantifies how well DIP 2.0's confidence scores align with actual outcomes.

Metrics implemented:
  - Brier Score: Mean squared error of probabilistic forecasts
  - Expected Calibration Error (ECE): Binned calibration error
  - Reliability Diagram data: Confidence vs. accuracy per bin
  - Sharpness: Variance of predictions (how decisive is the system?)
  - Overconfidence Score: Mean(max(0, confidence - accuracy))

References:
  - Guo et al. (2017) "On Calibration of Modern Neural Networks"
  - Brier (1950) "Verification of Forecasts Expressed in Terms of Probability"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class CalibrationPoint:
    """A single forecast-outcome pair for calibration analysis."""
    forecast_confidence: float   # 0.0–1.0, what the system predicted
    actual_outcome: float        # 0.0–1.0, what actually happened
    source: str = ""             # Which module produced this (minister, gate, etc.)
    label: str = ""              # Human-readable label


@dataclass
class CalibrationReport:
    """Complete calibration analysis."""
    points: List[CalibrationPoint] = field(default_factory=list)
    n_samples: int = 0
    brier_score: float = 0.0
    ece: float = 0.0              # Expected Calibration Error
    mce: float = 0.0              # Maximum Calibration Error
    sharpness: float = 0.0        # Variance of predictions
    overconfidence: float = 0.0    # Mean overconfidence
    reliability_bins: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""


def compute_brier_score(points: List[CalibrationPoint]) -> float:
    """
    Brier Score = (1/N) * Σ(forecast_i - outcome_i)²
    
    0 = perfect calibration, 1 = worst possible.
    Baseline (always predict 0.5) = 0.25.
    """
    if not points:
        return 1.0
    squared_errors = [(p.forecast_confidence - p.actual_outcome) ** 2 for p in points]
    return float(np.mean(squared_errors))


def compute_ece(
    points: List[CalibrationPoint],
    n_bins: int = 10,
) -> Tuple[float, float, List[Dict[str, Any]]]:
    """
    Expected Calibration Error (ECE).
    
    Partitions predictions into M bins, computes:
      ECE = Σ (|B_m| / N) * |acc(B_m) - conf(B_m)|
    
    Lower is better. 0 = perfect calibration.
    
    Returns: (ece, mce, reliability_bins)
    """
    if not points:
        return 1.0, 1.0, []
    
    confidences = np.array([p.forecast_confidence for p in points])
    outcomes = np.array([p.actual_outcome for p in points])
    
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bins: List[Dict[str, Any]] = []
    ece = 0.0
    mce = 0.0
    
    for i in range(n_bins):
        in_bin = (confidences >= bin_boundaries[i]) & (confidences < bin_boundaries[i + 1])
        # Last bin includes 1.0
        if i == n_bins - 1:
            in_bin = (confidences >= bin_boundaries[i]) & (confidences <= bin_boundaries[i + 1])
        
        n_in_bin = int(np.sum(in_bin))
        
        if n_in_bin == 0:
            bins.append({
                "bin": i,
                "range": f"{bin_boundaries[i]:.2f}-{bin_boundaries[i+1]:.2f}",
                "count": 0,
                "avg_confidence": 0.0,
                "avg_accuracy": 0.0,
                "gap": 0.0,
            })
            continue
        
        avg_confidence = float(np.mean(confidences[in_bin]))
        avg_accuracy = float(np.mean(outcomes[in_bin]))
        gap = abs(avg_accuracy - avg_confidence)
        
        ece += (n_in_bin / len(points)) * gap
        mce = max(mce, gap)
        
        bins.append({
            "bin": i,
            "range": f"{bin_boundaries[i]:.2f}-{bin_boundaries[i+1]:.2f}",
            "count": n_in_bin,
            "avg_confidence": round(avg_confidence, 4),
            "avg_accuracy": round(avg_accuracy, 4),
            "gap": round(gap, 4),
        })
    
    return round(ece, 4), round(mce, 4), bins


def compute_sharpness(points: List[CalibrationPoint]) -> float:
    """
    Sharpness = variance of forecast confidences.
    
    High sharpness = system makes decisive predictions (not always 0.5).
    Sharpness alone is neither good nor bad — must be paired with calibration.
    """
    if not points:
        return 0.0
    confidences = [p.forecast_confidence for p in points]
    return float(np.var(confidences))


def compute_overconfidence(points: List[CalibrationPoint]) -> float:
    """
    Overconfidence = mean(max(0, confidence - accuracy)).
    
    Positive = overconfident (predicts higher than actual).
    Negative = underconfident (predicts lower than actual).
    """
    if not points:
        return 0.0
    diffs = [max(0.0, p.forecast_confidence - p.actual_outcome) for p in points]
    return round(float(np.mean(diffs)), 4)


def build_calibration_report(
    points: List[CalibrationPoint],
    label: str = "DIP 2.0 Calibration Report",
) -> CalibrationReport:
    """Compute all calibration metrics from raw forecast-outcome pairs."""
    if not points:
        return CalibrationReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            n_samples=0,
        )
    
    brier = compute_brier_score(points)
    ece, mce, bins = compute_ece(points)
    sharpness = compute_sharpness(points)
    overconfidence = compute_overconfidence(points)
    
    return CalibrationReport(
        points=points,
        n_samples=len(points),
        brier_score=round(brier, 4),
        ece=ece,
        mce=mce,
        sharpness=round(sharpness, 4),
        overconfidence=overconfidence,
        reliability_bins=bins,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def points_from_backtest(evaluations: List[Any]) -> List[CalibrationPoint]:
    """
    Convert backtest evaluations to calibration points.
    
    Each evaluation has:
      - predicted_escalation → forecast_confidence
      - ground_truth_escalation → actual_outcome
    """
    points: List[CalibrationPoint] = []
    
    for ev in evaluations:
        forecast = getattr(ev, 'predicted_escalation', 0.5)
        actual = getattr(ev, 'crisis', None)
        if actual:
            actual_val = getattr(actual, 'ground_truth_escalation', 0.5)
        else:
            actual_val = 0.5
        
        crisis_name = getattr(ev, 'crisis', None)
        if crisis_name:
            label = getattr(crisis_name, 'name', 'Unknown')
        else:
            label = 'Unknown'
        
        points.append(CalibrationPoint(
            forecast_confidence=forecast,
            actual_outcome=actual_val,
            source="backtest",
            label=label,
        ))
    
    return points


def points_from_hypotheses(hypotheses: List[Any]) -> List[CalibrationPoint]:
    """
    Convert minister hypotheses to calibration points.
    Each hypothesis has a confidence; we treat 'has matched signals' as partial ground truth.
    """
    points: List[CalibrationPoint] = []
    
    for h in hypotheses:
        forecast = getattr(h, 'confidence', 0.5)
        # Heuristic ground truth: if hypothesis has matched signals, treat as
        # partially correct (0.7); if no matched signals, treat as less correct (0.3)
        matched = getattr(h, 'matched_signals', []) or []
        actual = 0.7 if len(matched) > 0 else 0.3
        
        label = f"{getattr(h, 'minister', 'Unknown')}: {getattr(h, 'hypothesis_type', 'unknown')}"
        
        points.append(CalibrationPoint(
            forecast_confidence=forecast,
            actual_outcome=actual,
            source="minister",
            label=label,
        ))
    
    return points


def print_calibration_report(report: CalibrationReport) -> str:
    """Format calibration report as readable string."""
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("  DIP 2.0 — CALIBRATION REPORT")
    lines.append("=" * 70)
    lines.append(f"  Samples:              {report.n_samples}")
    lines.append(f"  Brier Score:          {report.brier_score:.4f}  (0=perfect, 0.25=baseline, 1=worst)")
    lines.append(f"  ECE:                  {report.ece:.4f}  (Expected Calibration Error, lower=better)")
    lines.append(f"  MCE:                  {report.mce:.4f}  (Maximum Calibration Error)")
    lines.append(f"  Sharpness:            {report.sharpness:.4f}  (variance of predictions)")
    lines.append(f"  Overconfidence:       {report.overconfidence:+.4f}  (+ overconfident, - underconfident)")
    lines.append("")
    
    # Reliability Diagram (text-based)
    if report.reliability_bins:
        lines.append("  Reliability Diagram:")
        lines.append(f"  {'Bin':<6s} {'Range':<12s} {'Count':<7s} {'AvgConf':<10s} {'AvgAcc':<10s} {'Gap':<8s}")
        lines.append("  " + "-" * 55)
        for b in report.reliability_bins:
            lines.append(
                f"  {b['bin']:<6d} {b['range']:<12s} {b['count']:<7d} "
                f"{b['avg_confidence']:<10.4f} {b['avg_accuracy']:<10.4f} {b['gap']:<8.4f}"
            )
    lines.append("")
    
    # Interpretation
    if report.brier_score < 0.15:
        grade = "GOOD — System is well-calibrated (better than baseline 0.25)"
    elif report.brier_score < 0.25:
        grade = "ADEQUATE — Better than random, room for improvement"
    else:
        grade = "POOR — System is worse than always predicting 0.5"
    
    lines.append(f"  CALIBRATION GRADE: {grade}")
    
    if report.overconfidence > 0.05:
        lines.append(f"  [WARN] System is OVERCONFIDENT by {report.overconfidence:.4f} — predictions are too high")
    elif report.overconfidence < -0.05:
        lines.append(f"  [WARN] System is UNDERCONFIDENT by {abs(report.overconfidence):.4f} — predictions are too low")
    else:
        lines.append(f"  [OK] Overconfidence within acceptable range ({report.overconfidence:+.4f})")
    
    lines.append("=" * 70)
    
    return "\n".join(lines)


def export_calibration_json(report: CalibrationReport, path: Optional[Path] = None) -> Path:
    """Export calibration report as JSON."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "data" / "calibration_report.json"
    
    data = {
        "generated_at": report.generated_at,
        "n_samples": report.n_samples,
        "brier_score": report.brier_score,
        "ece": report.ece,
        "mce": report.mce,
        "sharpness": report.sharpness,
        "overconfidence": report.overconfidence,
        "reliability_bins": report.reliability_bins,
    }
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return path
