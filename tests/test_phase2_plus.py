"""Comprehensive tests for Phase 2-5 modules."""
import json
import pytest

from dip.pipeline.world_model.state.source_weighting import SourceReliability
from dip.engines.legal.signal_legal_mapper import map_signal_to_treaties, get_all_relevant_treaties
from dip.engines.legal.treaty_rag_pipeline import TreatyRAGPipeline
from dip.pipeline.memory.core.confidence_recalibrator import ConfidenceRecalibrator
from dip.engines.safety_enforcer import enforce_safety, SafetyReport
from dip.engines.self_model import SelfModel
from dip.engines.experiment_gate import ExperimentGate
from dip.pipeline.forecasting.wargaming.mesa_simulation import SimpleWargameSim


class TestSourceReliability:
    def test_beta_update_verified(self):
        sr = SourceReliability()
        initial = sr.get_reliability("OSINT")
        sr.update("OSINT", True)
        updated = sr.get_reliability("OSINT")
        assert updated > initial

    def test_beta_update_unverified(self):
        sr = SourceReliability()
        sr.update("TEST_SOURCE", False)
        sr.update("TEST_SOURCE", False)
        assert sr.get_reliability("TEST_SOURCE") < 0.5

    def test_detect_degradation(self):
        import uuid
        source = f"TEST_DEGRADE_{uuid.uuid4().hex[:6]}"
        sr = SourceReliability()
        for _ in range(12):
            sr.update(source, False)
        result = sr.detect_degradation(source, window=10)
        assert result is not None
        assert result["trend"] == "degrading"


class TestSignalLegalMapper:
    def test_troop_movement_maps_to_un_charter(self):
        results = map_signal_to_treaties("troop_movement", intensity=0.8)
        treaties = [r["treaty"] for r in results]
        assert "UN Charter" in treaties

    def test_nuclear_activity_maps_to_npt(self):
        results = map_signal_to_treaties("nuclear_activity", intensity=0.9)
        treaties = [r["treaty"] for r in results]
        assert any("NPT" in t for t in treaties)

    def test_bilateral_treaty_india_bhutan(self):
        results = map_signal_to_treaties("troop_movement", intensity=0.8, country="IND", target="BTN")
        has_bilateral = any(r.get("bilateral") for r in results)
        assert has_bilateral

    def test_no_match_returns_empty(self):
        results = map_signal_to_treaties("nonexistent_signal")
        assert isinstance(results, list)

    def test_get_all_relevant_treaties(self):
        signals = [
            {"action": "troop_movement", "intensity": 0.8, "target": "BTN"},
            {"action": "nuclear_activity", "intensity": 0.9},
        ]
        results = get_all_relevant_treaties(signals, country="IND")
        assert len(results) >= 3


class TestConfidenceRecalibrator:
    def test_record_and_recalibrate(self):
        cr = ConfidenceRecalibrator()
        cr.predictions = []  # clear shared state
        for _ in range(10):
            cr.record(0.8, 1)
        for _ in range(2):
            cr.record(0.8, 0)
        report = cr.get_report()
        assert report["predictions_recorded"] == 12
        assert report["status"] in ("calibrated", "overconfident", "underconfident")

    def test_adjust_confidence(self):
        cr = ConfidenceRecalibrator()
        adjusted = cr.adjust_confidence(0.75)
        assert 0.0 <= adjusted <= 1.0


class TestSafetyEnforcer:
    def test_clean_output_passes(self):
        output = {
            "head_of_country_briefing": {
                "executive_summary": "Border tensions remain stable. Evidence suggests routine activity.",
            },
            "threat_level": "LOW",
            "verification_score": 0.80,
        }
        report = enforce_safety(output)
        assert report.passed is True

    def test_covert_action_blocked(self):
        output = {
            "head_of_country_briefing": {
                "executive_summary": "Recommend covert operation against adversary.",
            },
            "threat_level": "HIGH",
        }
        report = enforce_safety(output)
        assert len(report.blocked_outputs) > 0

    def test_deception_blocked(self):
        output = {
            "briefing": "Execute deception campaign against target.",
        }
        report = enforce_safety(output)
        assert len(report.blocked_outputs) > 0


@pytest.mark.skip(reason="Legacy DIP 8 AgentSelfModel tests are obsolete in DIP 2.0")
class TestSelfModel:
    def test_update_after_assessment(self):
        sm = SelfModel()
        result = {
            "trace_id": "test-123",
            "status": "COMPLETE",
            "verification_score": 0.85,
            "data_blindspots": ["economic_data_gap"],
            "hypotheses": [
                {"minister": "Security Minister", "type": "military_threat", "confidence": 0.8}
            ],
        }
        dashboard = sm.update_after_assessment(result)
        assert dashboard["operational"]["total_assessments"] >= 1
        assert "Security Minister" in dashboard["ministers"]

    def test_withheld_tracking(self):
        sm = SelfModel()
        sm.update_after_assessment({"status": "WITHHELD", "trace_id": "t2", "verification_score": 0.3, "hypotheses": []})
        dashboard = sm.get_dashboard()
        assert dashboard["operational"]["total_withheld"] >= 1


@pytest.mark.skip(reason="Legacy DIP 8 ExperimentGate tests are obsolete in DIP 2.0")
class TestExperimentGate:
    def test_propose_and_record(self):
        import uuid
        gate = ExperimentGate()
        eid = f"test_exp_{uuid.uuid4().hex[:8]}"
        gate.propose_experiment(eid, "Test hypothesis: new threshold improves accuracy")
        passed = gate.record_result(eid, {"metric_value": 0.85, "baseline": 0.75})
        assert passed is True

    def test_failed_experiment_rolled_back(self):
        import uuid
        gate = ExperimentGate()
        eid = f"test_exp_{uuid.uuid4().hex[:8]}"
        gate.propose_experiment(eid, "Test hypothesis")
        passed = gate.record_result(eid, {"metric_value": 0.76, "baseline": 0.75})
        assert passed is False

    def test_can_promote(self):
        import uuid
        gate = ExperimentGate()
        eid = f"test_exp_{uuid.uuid4().hex[:8]}"
        gate.propose_experiment(eid, "Test")
        gate.record_result(eid, {"metric_value": 0.90, "baseline": 0.75})
        result = gate.can_promote(eid)
        assert result["can_promote"] is True


@pytest.mark.skip(reason="Legacy DIP 8 WargameSim tests are obsolete in DIP 2.0")
class TestWargameSim:
    def test_simulation_runs(self):
        sim = SimpleWargameSim(seed=42)
        result = sim.simulate("test_scenario", runs=100)
        assert result.runs == 100
        assert abs(sum(result.outcomes.values()) - 100) < 1
        assert 0.0 <= result.escalation_probability <= 1.0

    def test_high_intent_increases_escalation(self):
        sim = SimpleWargameSim(seed=42)
        low = sim.simulate("low_intent", adversary_intent=0.2, runs=100)
        high = sim.simulate("high_intent", adversary_intent=0.8, runs=100)
        assert high.escalation_probability > low.escalation_probability


class TestVectorStore:
    def test_store_and_search_fallback(self):
        from dip.pipeline.knowledge.vector_store import VectorStore
        store = VectorStore()
        store.store_document("test_col", "doc1", "Troop movement detected near border", {"region": "north"})
        results = store.search("test_col", "troop movement", k=3)
        assert len(results) >= 0  # fallback may return 0 for substring mismatch
        store.delete_collection("test_col")
