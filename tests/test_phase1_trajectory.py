"""Tests for Phase 1 modules: Trajectory, CSIS, ACH, Online Drift."""
from datetime import datetime, timezone

from dip.pipeline.forecasting.trajectory.prophet_forecaster import forecast_trajectory
from dip.pipeline.forecasting.trajectory.online_drift import OnlineDriftDetector
from dip.pipeline.forecasting.trajectory.csis_framework import (
    run_ach, run_red_team, run_devils_advocacy, run_scenario_planning,
)
from dip.pipeline.deliberation.reasoning.hypothesis_tracker import (
    HypothesisTracker, create_default_hypotheses,
)


class TestProphetForecaster:
    def test_numpy_fallback_forecasts(self):
        scores = [
            {"timestamp": "2026-06-01T00:00:00", "sre_score": 0.30},
            {"timestamp": "2026-06-08T00:00:00", "sre_score": 0.35},
            {"timestamp": "2026-06-15T00:00:00", "sre_score": 0.40},
            {"timestamp": "2026-06-22T00:00:00", "sre_score": 0.48},
            {"timestamp": "2026-06-29T00:00:00", "sre_score": 0.55},
        ]
        result = forecast_trajectory(scores, horizon_days=7)
        assert 0.0 <= result["forecast_7d"] <= 1.0
        assert result["trend"] in ("ESCALATING", "STABLE", "DE_ESCALATING")
        assert result["method"] in ("prophet", "numpy_fallback")

    def test_insufficient_data(self):
        result = forecast_trajectory([], horizon_days=7)
        assert result["method"] == "insufficient_data"
        assert result["forecast_7d"] == 0.0


class TestOnlineDrift:
    def test_normal_values_no_anomaly(self):
        detector = OnlineDriftDetector(window_size=10)
        results = []
        for i, score in enumerate([0.3, 0.32, 0.31, 0.33, 0.30, 0.34, 0.32, 0.31]):
            r = detector.update(f"t{i}", score)
            results.append(r)
        # No anomalies for stable series
        anomaly_count = sum(1 for r in results if r["is_anomaly"])
        assert anomaly_count <= 1  # at most 1 false positive

    def test_spike_detected_as_anomaly(self):
        detector = OnlineDriftDetector(window_size=10)
        for i, score in enumerate([0.3, 0.31, 0.32, 0.30, 0.33, 0.31, 0.32]):
            detector.update(f"t{i}", score)
        # Spike
        result = detector.update("spike", 0.95)
        assert result["is_anomaly"] is True or result["z_score"] > 2.0


class TestCSISFramework:
    def test_ach_scoring(self):
        evidence = ["troop_movement", "sanctions", "diplomatic_opening"]
        scores = {
            "imminent_attack": {"troop_movement": 0.8, "sanctions": 0.3, "diplomatic_opening": -0.5},
            "saber_rattling": {"troop_movement": 0.4, "sanctions": 0.6, "diplomatic_opening": 0.2},
        }
        result = run_ach(["imminent_attack", "saber_rattling"], evidence, scores)
        assert result.most_likely in ("imminent_attack", "saber_rattling")
        assert result.most_likely_score > 0.0

    def test_red_team_challenges(self):
        result = run_red_team("Imminent attack", ["troop_movement"], 0.85)
        assert "evidence_gaps" in result
        assert "alternative_explanations" in result
        assert "mirror_imaging" in result

    def test_devils_advocacy(self):
        result = run_devils_advocacy("Imminent attack", 0.85)
        assert "counter_narrative" in result
        assert "base_rate" in result

    def test_scenario_planning(self):
        result = run_scenario_planning("border tension", ["troop_buildup", "rhetoric"], 30)
        assert len(result.branches) == 4
        assert result.baseline == "Baseline"
        assert result.pessimistic == "Pessimistic"


class TestHypothesisTracker:
    def test_bayesian_update(self):
        tracker = HypothesisTracker(create_default_hypotheses())
        report = tracker.update_evidence("troop_movement_observed", {
            "imminent_escalation": 0.8,
            "coercive_signaling": 0.5,
            "domestic_posturing": 0.2,
            "routine_activity": 0.05,
            "third_party_manipulation": 0.1,
        })
        assert report.most_likely in ("imminent_escalation", "coercive_signaling")
        assert 0.0 <= report.most_likely_prob <= 1.0

    def test_convergence_after_multiple_updates(self):
        tracker = HypothesisTracker(create_default_hypotheses())
        for i in range(5):
            report = tracker.update_evidence(f"evidence_{i}", {
                "imminent_escalation": 0.7 + i * 0.05,
                "coercive_signaling": 0.3,
                "domestic_posturing": 0.1,
                "routine_activity": 0.05,
                "third_party_manipulation": 0.05,
            })
        assert report.most_likely == "imminent_escalation"

    def test_default_hypotheses_created(self):
        hypotheses = create_default_hypotheses()
        assert len(hypotheses) == 5
        total_prior = sum(h["prior"] for h in hypotheses)
        assert abs(total_prior - 1.0) < 0.01
