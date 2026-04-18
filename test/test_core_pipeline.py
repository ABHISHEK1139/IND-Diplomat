"""
IND-Diplomat — Core Pipeline Unit Tests
=========================================
Validates the critical-path modules that form the backbone of the system.
Tests are designed to run without external services (Ollama, Redis, Neo4j).

Tests importing from app_server require FastAPI to be installed and will
be skipped gracefully if it's not available.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Ensure project root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(str(_ROOT))

# ── Conditional imports: skip tests if fastapi is not installed ────────────
_has_fastapi = True
try:
    import fastapi  # noqa: F401
except ImportError:
    _has_fastapi = False

needs_fastapi = pytest.mark.skipif(
    not _has_fastapi,
    reason="FastAPI not installed — install with: pip install fastapi uvicorn"
)


# ═══════════════════════════════════════════════════════════════════════════
# Configuration Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestConfig:
    """Validate configuration module loads correctly."""

    def test_project_root_exists(self):
        from Config.config import PROJECT_ROOT
        assert PROJECT_ROOT.exists(), f"PROJECT_ROOT does not exist: {PROJECT_ROOT}"

    def test_project_root_is_directory(self):
        from Config.config import PROJECT_ROOT
        assert PROJECT_ROOT.is_dir()

    def test_llm_provider_has_value(self):
        from Config.config import LLM_PROVIDER
        assert LLM_PROVIDER in {"ollama", "openrouter", "litellm"}, \
            f"Unexpected LLM_PROVIDER: {LLM_PROVIDER}"

    def test_cors_origins_is_list(self):
        from Config.config import CORS_ALLOWED_ORIGINS
        assert isinstance(CORS_ALLOWED_ORIGINS, list)
        assert len(CORS_ALLOWED_ORIGINS) > 0

    def test_env_flag_helper(self):
        from Config.config import _env_flag
        assert _env_flag("__NONEXISTENT__", "true") is True
        assert _env_flag("__NONEXISTENT__", "false") is False

    def test_config_print_runs(self, capsys):
        from Config.config import print_config
        print_config()
        captured = capsys.readouterr()
        assert "PROJECT_ROOT" in captured.out


# ═══════════════════════════════════════════════════════════════════════════
# DiplomatResult Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDiplomatResult:
    """Validate the result dataclass used across all API surfaces."""

    def test_basic_creation(self):
        from run import DiplomatResult
        result = DiplomatResult(
            outcome="ASSESSMENT",
            answer="Test answer",
            confidence=0.85,
            risk_level="MEDIUM",
            trace_id="test-trace-001",
        )
        assert result.outcome == "ASSESSMENT"
        assert result.confidence == 0.85
        assert result.risk_level == "MEDIUM"

    def test_to_dict_excludes_raw_by_default(self):
        from run import DiplomatResult
        result = DiplomatResult(outcome="ASSESSMENT", answer="x")
        d = result.to_dict()
        assert "whitebox" not in d
        assert d["outcome"] == "ASSESSMENT"

    def test_to_dict_includes_whitebox(self):
        from run import DiplomatResult
        result = DiplomatResult(outcome="ASSESSMENT", answer="x")
        d = result.to_dict(whitebox=True)
        assert "whitebox" in d
        assert isinstance(d["whitebox"], dict)

    def test_to_dict_includes_run_log(self):
        from run import DiplomatResult
        result = DiplomatResult(
            outcome="ASSESSMENT",
            answer="x",
            run_log=["step1", "step2"],
        )
        d = result.to_dict(include_run_log=True)
        assert "run_log" in d
        assert len(d["run_log"]) == 2

    def test_raw_property_is_readonly(self):
        from run import DiplomatResult
        result = DiplomatResult(outcome="ASSESSMENT", _raw={"test": True})
        assert result.raw == {"test": True}

    def test_confidence_clamping(self):
        from run import DiplomatResult
        result = DiplomatResult(outcome="ASSESSMENT", confidence=1.5)
        d = result.to_dict()
        # Confidence is stored as-is; clamping is done at display
        assert d["confidence"] == 1.5


# ═══════════════════════════════════════════════════════════════════════════
# Signal Mapping Tests
# ═══════════════════════════════════════════════════════════════════════════

@needs_fastapi
class TestSignalMapping:
    """Validate SRE signal-to-dimension mapping used in evidence chains."""

    def test_known_capability_signals(self):
        sys.path.insert(0, str(_ROOT))
        # Import the mapping from app_server
        from app_server import _SIGNAL_DIM

        capability_signals = [
            "SIG_MIL_MOBILIZATION", "SIG_MIL_ESCALATION",
            "SIG_FORCE_POSTURE", "SIG_CYBER_ACTIVITY",
        ]
        for sig in capability_signals:
            assert _SIGNAL_DIM.get(sig) == "CAPABILITY", f"{sig} should map to CAPABILITY"

    def test_known_intent_signals(self):
        from app_server import _SIGNAL_DIM
        intent_signals = [
            "SIG_DIP_HOSTILITY", "SIG_DIPLOMACY_ACTIVE",
            "SIG_COERCIVE_BARGAINING", "SIG_ALLIANCE_ACTIVATION",
        ]
        for sig in intent_signals:
            assert _SIGNAL_DIM.get(sig) == "INTENT", f"{sig} should map to INTENT"

    def test_known_stability_signals(self):
        from app_server import _SIGNAL_DIM
        stability_signals = [
            "SIG_INTERNAL_INSTABILITY", "SIG_PUBLIC_PROTEST",
            "SIG_ELITE_FRACTURE",
        ]
        for sig in stability_signals:
            assert _SIGNAL_DIM.get(sig) == "STABILITY", f"{sig} should map to STABILITY"

    def test_known_cost_signals(self):
        from app_server import _SIGNAL_DIM
        cost_signals = [
            "SIG_ECONOMIC_PRESSURE", "SIG_ECO_SANCTIONS_ACTIVE",
            "SIG_SANCTIONS_ACTIVE",
        ]
        for sig in cost_signals:
            assert _SIGNAL_DIM.get(sig) == "COST", f"{sig} should map to COST"

    def test_unknown_signal_returns_none(self):
        from app_server import _SIGNAL_DIM
        assert _SIGNAL_DIM.get("SIG_NONEXISTENT") is None


# ═══════════════════════════════════════════════════════════════════════════
# Evidence Chain Builder Tests
# ═══════════════════════════════════════════════════════════════════════════

@needs_fastapi
class TestEvidenceChainBuilder:
    """Validate the evidence chain construction from council sessions."""

    def test_empty_session(self):
        from app_server import _build_evidence_chain
        chain = _build_evidence_chain({})
        assert chain == []

    def test_dict_evidence_items(self):
        from app_server import _build_evidence_chain
        cs = {
            "evidence_log": [
                {
                    "signal_name": "SIG_MIL_MOBILIZATION",
                    "confidence": 0.8,
                    "source_type": "GDELT",
                    "source_detail": "Troop movements reported",
                },
                {
                    "signal": "SIG_DIP_HOSTILITY",
                    "confidence": 0.6,
                    "dimension": "INTENT",
                },
            ]
        }
        chain = _build_evidence_chain(cs)
        assert len(chain) == 2
        assert chain[0]["signal_name"] == "SIG_MIL_MOBILIZATION"
        assert chain[0]["dimension"] == "CAPABILITY"
        assert chain[1]["dimension"] == "INTENT"

    def test_string_evidence_items(self):
        from app_server import _build_evidence_chain
        cs = {"evidence_log": ["SIG_ECONOMIC_PRESSURE"]}
        chain = _build_evidence_chain(cs)
        assert len(chain) == 1
        assert chain[0]["dimension"] == "COST"
        assert chain[0]["source_type"] == "text"

    def test_max_30_items(self):
        from app_server import _build_evidence_chain
        cs = {"evidence_log": [{"signal_name": f"sig_{i}"} for i in range(50)]}
        chain = _build_evidence_chain(cs)
        assert len(chain) == 30


# ═══════════════════════════════════════════════════════════════════════════
# Reasoning Chain Builder Tests
# ═══════════════════════════════════════════════════════════════════════════

@needs_fastapi
class TestReasoningChainBuilder:
    """Validate reasoning chain construction."""

    def test_empty_result_returns_empty(self):
        from run import DiplomatResult
        from app_server import _build_reasoning_chain
        result = DiplomatResult(outcome="ASSESSMENT", answer="x")
        chain = _build_reasoning_chain(result)
        assert chain == []

    def test_minister_reasoning_empty_session(self):
        from app_server import _build_minister_reasoning
        steps = _build_minister_reasoning({})
        assert steps == []

    def test_minister_reasoning_with_reports(self):
        from app_server import _build_minister_reasoning
        cs = {
            "minister_reports": {
                "Security": {
                    "confidence": 0.75,
                    "dimension": "CAPABILITY",
                    "primary_drivers": ["troop_movement"],
                    "critical_gaps": [],
                    "reasoning_text": "Military buildup observed",
                },
                "Economic": {
                    "confidence": 0.6,
                    "dimension": "COST",
                },
            }
        }
        steps = _build_minister_reasoning(cs)
        assert len(steps) == 2
        assert steps[0]["title"] == "Minister: Security"
        assert "CAPABILITY" in steps[0]["description"]


# ═══════════════════════════════════════════════════════════════════════════
# Job Store Tests
# ═══════════════════════════════════════════════════════════════════════════

@needs_fastapi
class TestJobStore:
    """Validate the in-memory job store for async assessments."""

    def test_create_job(self, tmp_path):
        from app_server import JobStore
        store = JobStore(persist_path=tmp_path / "jobs.json")
        jid = store.create("Test query", {"country_code": "IND"})
        assert isinstance(jid, str)
        assert len(jid) == 12

    def test_get_job(self, tmp_path):
        from app_server import JobStore
        store = JobStore(persist_path=tmp_path / "jobs.json")
        jid = store.create("Test query", {})
        job = store.get(jid)
        assert job is not None
        assert job.query == "Test query"
        assert job.status == "QUEUED"

    def test_update_job(self, tmp_path):
        from app_server import JobStore
        store = JobStore(persist_path=tmp_path / "jobs.json")
        jid = store.create("Test query", {})
        store.update(jid, status="RUNNING", progress_pct=50)
        job = store.get(jid)
        assert job.status == "RUNNING"
        assert job.progress_pct == 50

    def test_list_recent(self, tmp_path):
        from app_server import JobStore
        store = JobStore(persist_path=tmp_path / "jobs.json")
        store.create("Query 1", {})
        store.create("Query 2", {})
        recent = store.list_recent(limit=5)
        assert len(recent) == 2

    def test_max_jobs_eviction(self, tmp_path):
        from app_server import JobStore
        store = JobStore(max_jobs=3, persist_path=tmp_path / "jobs.json")
        ids = [store.create(f"Query {i}", {}) for i in range(5)]
        # Only 3 should remain
        recent = store.list_recent(limit=10)
        assert len(recent) == 3

    def test_persistence_round_trip(self, tmp_path):
        from app_server import JobStore
        persist_file = tmp_path / "jobs.json"
        store1 = JobStore(persist_path=persist_file)
        jid = store1.create("Persistent query", {"country": "IND"})
        store1.update(jid, status="COMPLETED", risk_level="HIGH")

        # Create new store from same file
        store2 = JobStore(persist_path=persist_file)
        job = store2.get(jid)
        assert job is not None
        assert job.query == "Persistent query"
        assert job.status == "COMPLETED"
        assert job.risk_level == "HIGH"


# ═══════════════════════════════════════════════════════════════════════════
# Utility Function Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestUtilityFunctions:
    """Validate utility functions used across the pipeline."""

    @needs_fastapi
    def test_safe_serializes_primitives(self):
        from app_server import _safe
        assert _safe("hello") == "hello"
        assert _safe(42) == 42
        assert _safe(3.14) == 3.14
        assert _safe(True) is True
        assert _safe(None) is None

    @needs_fastapi
    def test_safe_serializes_dicts(self):
        from app_server import _safe
        result = _safe({"a": 1, "b": [2, 3]})
        assert result == {"a": 1, "b": [2, 3]}

    @needs_fastapi
    def test_safe_handles_nested_objects(self):
        from app_server import _safe

        class MockObj:
            def __init__(self):
                self.value = 42
                self._internal = "hidden"

        result = _safe(MockObj())
        assert result["value"] == 42
        assert "_internal" not in result

    @needs_fastapi
    def test_to_ratio_clamps_values(self):
        from app_server import _to_ratio
        assert _to_ratio(0.5) == 0.5
        assert _to_ratio(1.5) == 1.0
        assert _to_ratio(-0.5) == 0.0
        assert _to_ratio("invalid") == 0.0

    def test_json_safe_redacts_secrets(self):
        from run import _json_safe
        result = _json_safe({"api_key": "super_secret", "name": "test"})
        assert result["api_key"] == "***REDACTED***"
        assert result["name"] == "test"

    def test_json_safe_redacts_nested_secrets(self):
        from run import _json_safe
        result = _json_safe({"config": {"password": "abc123", "host": "localhost"}})
        assert result["config"]["password"] == "***REDACTED***"
        assert result["config"]["host"] == "localhost"

    def test_is_sensitive_key(self):
        from run import _is_sensitive_key
        assert _is_sensitive_key("api_key") is True
        assert _is_sensitive_key("API_KEY") is True
        assert _is_sensitive_key("password") is True
        assert _is_sensitive_key("name") is False
        assert _is_sensitive_key("host") is False

    def test_check_ollama_returns_dict(self):
        from run import _check_ollama
        result = _check_ollama()
        assert isinstance(result, dict)
        assert "ok" in result
        assert "provider" in result


# ═══════════════════════════════════════════════════════════════════════════
# Threshold Configuration Tests
# ═══════════════════════════════════════════════════════════════════════════

@needs_fastapi
class TestThresholds:
    """Validate signal threshold configuration."""

    def test_thresholds_importable(self):
        from Config.thresholds import SignalThresholds
        assert hasattr(SignalThresholds, "ESCALATION_CRITICAL")

    def test_thresholds_are_numeric(self):
        from Config.thresholds import SignalThresholds
        t = SignalThresholds()
        # All public attributes should be numeric
        for attr in dir(t):
            if not attr.startswith("_") and not callable(getattr(t, attr)):
                value = getattr(t, attr)
                assert isinstance(value, (int, float)), \
                    f"Threshold {attr} = {value} is not numeric"


# ═══════════════════════════════════════════════════════════════════════════
# V2 Response Mapping Tests
# ═══════════════════════════════════════════════════════════════════════════

@needs_fastapi
class TestV2ResponseMapping:
    """Validate the DiplomatResult → API response mapping."""

    def test_assessment_response(self):
        from run import DiplomatResult
        from app_server import _map_v2_response

        result = DiplomatResult(
            outcome="ASSESSMENT",
            answer="Risk assessment completed",
            confidence=0.75,
            risk_level="MEDIUM",
            trace_id="trace-001",
            elapsed_seconds=12.5,
        )
        resp = _map_v2_response(result)
        assert resp["success"] is True
        assert resp["outcome"] == "ASSESSMENT"
        assert resp["confidence"] == 0.75
        assert resp["risk_level"] == "MEDIUM"
        assert resp["latency_ms"] == 12500

    def test_out_of_scope_response(self):
        from run import DiplomatResult
        from app_server import _map_v2_response

        result = DiplomatResult(
            outcome="OUT_OF_SCOPE",
            answer="This query is outside our domain.",
            confidence=0.0,
            elapsed_seconds=0.5,
        )
        resp = _map_v2_response(result)
        assert resp["success"] is False
        assert resp["outcome"] == "OUT_OF_SCOPE"

    def test_insufficient_evidence_response(self):
        from run import DiplomatResult
        from app_server import _map_v2_response

        result = DiplomatResult(
            outcome="INSUFFICIENT_EVIDENCE",
            answer="Not enough data.",
            confidence=0.3,
            elapsed_seconds=5.0,
        )
        resp = _map_v2_response(result)
        assert resp["success"] is False
        assert resp["outcome"] == "INSUFFICIENT_EVIDENCE"
