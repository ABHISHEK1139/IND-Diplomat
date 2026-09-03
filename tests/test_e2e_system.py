import pytest
import tempfile
import os
from pathlib import Path
from dip.core.schema import StateContext, Signal, WargameAction, WargameResult
from dip.pipeline.forecasting.wargaming.scenario_engine import run_wargame
from dip.engines.multiformat_exporter import export_all

@pytest.mark.asyncio
@pytest.mark.unit
async def test_wargaming_simulation_e2e(monkeypatch):
    """Verify wargaming engine simulates downstream escalation and spillovers."""
    async def mock_translate(action):
        return [
            Signal(
                entity="COUNTRY_A",
                action="SIG_MIL_REDEPLOYMENT",
                target="COUNTRY_B",
                intensity=0.8,
                confidence=1.0,
                source_ref="WARGAME_SIM",
                domain="military"
            )
        ]
    async def mock_synthesize(*args, **kwargs):
        return "Simulated consequence briefing: heightened deterrence posture."

    monkeypatch.setattr("dip.pipeline.forecasting.wargaming.scenario_engine.translate_action_to_signals", mock_translate)
    monkeypatch.setattr("dip.pipeline.forecasting.wargaming.scenario_engine.synthesize_consequences", mock_synthesize)

    initial_context = StateContext(
        country="IND",
        current_signals=[
            Signal(
                entity="IND",
                action="SIG_DIPLOMACY_ACTIVE",
                intensity=0.4,
                confidence=0.9,
                source_ref="test",
                domain="diplomatic"
            )
        ]
    )

    action = WargameAction(
        description="Deploy naval task force to Malacca Strait",
        target_country="CHN"
    )

    result = await run_wargame(initial_context, action)
    assert isinstance(result, WargameResult)
    assert result.action.description == action.description
    assert len(result.synthetic_signals) == 1
    assert isinstance(result.global_spillovers, dict)
    assert result.consequence_briefing != ""
    assert result.simulation_outcomes is not None


@pytest.mark.unit
def test_multiformat_exporter_e2e():
    """Verify export_all writes JSON, Markdown, and CSV without serialization errors."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        sample_result = {
            "trace_id": "test_e2e_trace_999",
            "query": "Assess naval movements in Taiwan Strait",
            "country": "TWN",
            "threat_level": "ELEVATED",
            "verification_score": 0.85,
            "strategic_narrative_md": "# Strategic Assessment\nNaval activity heightened.",
            "research_log": [
                {
                    "query": "Taiwan naval patrols",
                    "priority": "HIGH",
                    "status": "COMPLETED",
                    "evidence_found": 3,
                    "cost_usd": 0.01,
                    "time_ms": 250
                }
            ]
        }

        paths = export_all(sample_result, session=None, output_dir=tmp_dir)

        assert "json" in paths
        assert Path(paths["json"]).exists()

        assert "markdown" in paths
        assert Path(paths["markdown"]).exists()

        assert "csv" in paths
        assert Path(paths["csv"]).exists()
