"""Final integration tests for Phase 3-6 modules."""
from dip.layer7_global.cross_theater_forecaster import forecast_cross_theater, COUNTRY_THEATER
import pytest
from dip.layer4_reasoning.minister_curriculum import MinisterCurriculum
from dip.SystemGuardian.guardian_agent import SystemGuardian


class TestCrossTheaterForecaster:
    def test_forecast_returns_theaters(self):
        result = forecast_cross_theater("IND", 0.7)
        assert result["source_theater"] == "south_asia"
        assert len(result["theater_scores"]) >= 1

    def test_forecast_decay(self):
        result = forecast_cross_theater("IND", 0.5, decay_factor=0.3, max_hops=1)
        for score in result["theater_scores"].values():
            assert score <= 0.5

    def test_recommendations_for_high_contagion(self):
        result = forecast_cross_theater("IND", 0.9)
        assert len(result["recommendations"]) >= 1





class TestMinisterCurriculum:
    def test_assess_generates_targets(self):
        mc = MinisterCurriculum()
        targets = mc.assess_from_replay("Security Minister", 0.55, [])
        assert len(targets) >= 1
        assert any(t.skill == "confidence_calibration" for t in targets)

    def test_get_next_target(self):
        mc = MinisterCurriculum()
        mc.assess_from_replay("Economic Minister", 0.50, [])
        target = mc.get_next_target("Economic Minister")
        assert target is not None
        assert target.priority > 0.5


class TestSystemGuardian:
    def test_full_health_report(self):
        sg = SystemGuardian()
        report = sg.full_health_report()
        assert "healthy" in report
        assert "checks" in report
        assert "disk_space" in report["checks"]
        assert "llm_availability" in report["checks"]

    def test_health_history_accumulates(self):
        sg = SystemGuardian()
        sg.full_health_report()
        sg.full_health_report()
        assert len(sg.health_history) >= 2
