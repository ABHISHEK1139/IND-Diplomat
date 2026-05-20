import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Ensure project root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(str(_ROOT))

from engine.Layer4_Analysis.core.unified_pipeline import (
    UnifiedPipeline,
    OUTCOME_INSUFFICIENT_EVIDENCE,
)


def test_pipeline_outcome_shape_on_llm_block():
    pipeline = UnifiedPipeline()
    health_report = {
        "overall_ok": False,
        "failed_checks": ["ollama"],
        "checks": {
            "ollama": {
                "ok": False,
                "provider": "openrouter",
                "error": "unreachable",
            }
        },
    }

    with patch(
        "engine.Layer4_Analysis.core.system_guardian.run_full_system_check",
        return_value=health_report,
    ), patch(
        "engine.Layer4_Analysis.core.system_guardian.summarize_blockers",
        return_value=["ollama: unreachable"],
    ):
        result = asyncio.run(
            pipeline.execute(
                query="Assess conflict risk between India and China.",
                country_code="IND",
            )
        )

    assert result.outcome == OUTCOME_INSUFFICIENT_EVIDENCE
    assert result.status == "LLM_UNREACHABLE"
    assert isinstance(result.answer, str) and result.answer.strip()
