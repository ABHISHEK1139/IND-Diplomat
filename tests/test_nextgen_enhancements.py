from dip.engines.oss_adapters import OSSAdapterRegistry
from dip.engines.networkx_adapter import create_networkx_adapter
from dip.engines.crisis_replay import CrisisReplayBenchmark, ReplayCase


def test_oss_adapter_registry_has_expected_capabilities():
    registry = OSSAdapterRegistry()
    status = registry.status()
    names = {row["name"] for row in status}
    assert "LangGraph" in names
    assert "Prefect" in names
    assert "OpenTelemetry" in names
    assert "MLflow" in names
    assert "NetworkX" in names


def test_networkx_adapter_factory_is_safe_without_env():
    adapter = create_networkx_adapter()
    assert adapter is None or hasattr(adapter, "compute_contagion")


def test_crisis_replay_benchmark_summarize():
    benchmark = CrisisReplayBenchmark([
        ReplayCase(name="case1", query="brief on case1", country="IND", min_verification_score=0.0),
        ReplayCase(name="case2", query="brief on case2", country="CXY", min_verification_score=0.0),
    ])
    summary = benchmark.summarize([])
    assert summary["total"] == 0
    assert summary["pass_rate"] == 0.0
