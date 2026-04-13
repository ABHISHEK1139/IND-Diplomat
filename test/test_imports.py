import sys, os
proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, proj)
os.chdir(proj)

from test._support import script_log_path

CHECKS = [
    ("L1-observation", "from engine.Layer1_Collection.observation import ObservationRecord"),
    ("L1-gdelt", "from engine.Layer1_Collection import GDELTSensor"),
    ("L2-retriever", "from engine.Layer2_Knowledge.retriever import DiplomaticRetriever"),
    ("L2-knowledge-api", "from engine.Layer2_Knowledge.knowledge_api import KnowledgeAPI"),
    ("L2-vector-store", "from engine.Layer2_Knowledge.vector_store import get_vector_store"),
    ("L2-multi-index", "from engine.Layer2_Knowledge.multi_index import multi_index_manager"),
    ("L2-entity-reg", "from engine.Layer2_Knowledge.entity_registry import entity_registry"),
    ("L2-source-reg", "from engine.Layer2_Knowledge.source_registry import source_registry"),
    ("L3-state-context", "from engine.Layer3_StateModel.schemas.state_context import StateContext"),
    ("L3-precursor", "from engine.Layer3_StateModel.temporal.precursor_monitor import PrecursorMonitor"),
    ("L3-country-builder", "from engine.Layer3_StateModel.construction.country_state_builder import CountryStateBuilder"),
    ("L3-readiness", "from engine.Layer3_StateModel.construction.analysis_readiness import evaluate_analysis_readiness"),
    ("L3-state-provider", "from importlib import import_module; import_module('engine.Layer3_StateModel.interface.state_provider')"),
    ("Core-knowledge-port", "from Core.orchestrator.knowledge_port import knowledge_port"),
    ("L4-llm-client", "from importlib import import_module; import_module('engine.Layer4_Analysis.core.llm_client')"),
    ("L4-coordinator", "from importlib import import_module; import_module('engine.Layer4_Analysis.coordinator')"),
    ("Config-config", "from Config.config import PROJECT_ROOT, LLM_MODEL"),
    ("Config-pipeline", "from Config.pipeline import initialize, run_query"),
]


def _run_checks():
    results = []
    for label, stmt in CHECKS:
        try:
            exec(stmt, {})
            results.append(("OK", label, ""))
        except Exception as exc:
            results.append(("FAIL", label, str(exc)))
    return results


def test_imports_smoke():
    results = _run_checks()
    out = open(script_log_path("full_import_results.log"), "w", encoding="utf-8")
    try:
        for status, label, detail in results:
            if status == "OK":
                out.write(f"OK: {label}\n")
            else:
                out.write(f"FAIL: {label}: {detail}\n")
        ok = sum(1 for status, _, _ in results if status == "OK")
        out.write(f"\n{ok}/{len(results)} passed\n")
    finally:
        out.close()

    failures = [f"{label}: {detail}" for status, label, detail in results if status == "FAIL"]
    assert not failures, "Import smoke test failures: " + "; ".join(failures)
