"""Tests for Phase 1-5 completion modules."""
import pytest
from dip.layer5_trajectory.granger_causality import find_causal_chains
from dip.layer4_reasoning.sre_parity import (
    run_counterfactual, generate_curiosity_questions,
    assess_epistemic_needs, detect_intelligence_gaps, compute_war_index,
)
from dip.layer8_wargaming.nash_equilibrium import compute_equilibrium
from dip.nextgen.replay_consolidation import ReplayConsolidator



class TestGranger:
    def test_correlation_fallback(self):
        series = {
            "troop_movement": [0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8],
            "diplomatic_recall": [0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6],
        }
        results = find_causal_chains(series)
        assert isinstance(results, list)


class TestCounterfactual:
    def test_removing_minister_changes_avg(self):
        session = type("s", (), {"hypotheses": [
            type("h", (), {"minister": "Security", "confidence": 0.8})(),
            type("h", (), {"minister": "Diplomacy", "confidence": 0.6})(),
            type("h", (), {"minister": "Economic", "confidence": 0.4})(),
        ]})()
        result = run_counterfactual(session, "Security")
        assert result["original_avg_confidence"] != result["counterfactual_avg_confidence"]


class TestCuriosity:
    def test_generates_questions(self):
        session = type("s", (), {"hypotheses": [
            type("h", (), {"minister": "Security", "confidence": 0.9, "hypothesis_type": "threat"})(),
            type("h", (), {"minister": "Diplomacy", "confidence": 0.3, "hypothesis_type": "posture"})(),
        ], "missing_signals": ["satellite_imagery"]})()
        questions = generate_curiosity_questions(session)
        assert len(questions) >= 1


class TestEpistemicNeeds:
    def test_military_gaps_are_critical(self):
        session = type("s", (), {"missing_signals": ["military_deployment_data"], "evidence_log": []})()
        needs = assess_epistemic_needs(session)
        assert len(needs["critical_gaps"]) >= 1


class TestGapEngine:
    def test_low_capability_is_critical(self):
        gaps = detect_intelligence_gaps({"capability": 0.2, "intent": 0.6, "stability": 0.5, "cost": 0.4}, 0.6, ["g1"])
        assert gaps["domain_gaps"]["capability"]["priority"] == "CRITICAL"
        assert gaps["domain_gaps"]["intent"]["priority"] == "LOW"


class TestWarIndex:
    def test_high_capability_intent_yields_high_war_index(self):
        result = compute_war_index(capability=0.8, intent=0.7, stability=0.6, cost=0.3)
        assert result["war_index"] > 0.4
        assert result["level"] in ("HIGH", "CRITICAL")

    def test_low_inputs_yield_low_index(self):
        result = compute_war_index(capability=0.1, intent=0.1, stability=0.8, cost=0.2)
        assert result["war_index"] < 0.3


@pytest.mark.skip(reason="Legacy API")
class TestNashEquilibrium:
    def test_computes_strategies(self):
        result = compute_equilibrium(capability=0.6, intent=0.5, stability=0.4, cost=0.3)
        assert "nash_equilibrium" in result
        assert "adversary" in result["nash_equilibrium"]
        assert "risk_assessment" in result


class TestReplayConsolidation:
    def test_record_and_consolidate(self):
        rc = ReplayConsolidator()
        rc.replay_results = []  # clear
        for _ in range(5):
            rc.record_replay("scenario_1", "HIGH", "HIGH", 0.8)
        for _ in range(3):
            rc.record_replay("scenario_2", "LOW", "HIGH", 0.7)
        report = rc.get_report()
        assert report["replays"] >= 5
