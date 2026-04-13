"""Verify all renamed imports work correctly after the 10/10 cleanup."""
import sys, os, traceback
proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, proj)

from test._support import script_log_path

out = open(script_log_path("rename_verify.log"), "w", encoding="utf-8")
passed = 0
failed = 0

def test(label, import_fn):
    global passed, failed
    try:
        import_fn()
        out.write(f"PASS: {label}\n")
        passed += 1
    except Exception:
        out.write(f"FAIL: {label}\n")
        traceback.print_exc(file=out)
        out.write("\n")
        failed += 1

# ── Layer 1 (renamed sensor folders) ──
test("LAYER1 GDELTSensor",         lambda: __import__("LAYER1_COLLECTION").GDELTSensor)
test("LAYER1 WorldBankSensor",     lambda: __import__("LAYER1_COLLECTION").WorldBankSensor)
test("LAYER1 ComtradeSensor",      lambda: __import__("LAYER1_COLLECTION").ComtradeSensor)
test("LAYER1 collect_all",         lambda: __import__("LAYER1_COLLECTION").collect_all)
test("LAYER1 api.worldbank",       lambda: __import__("LAYER1_COLLECTION.api.worldbank.sensor", fromlist=["WorldBankSensor"]))
test("LAYER1 api.comtrade",        lambda: __import__("LAYER1_COLLECTION.api.comtrade.sensor", fromlist=["ComtradeSensor"]))

# ── Layer 2 (renamed subfolders) ──
test("L2 storage.vector_store",    lambda: __import__("Layer2_Knowledge.storage.vector_store", fromlist=["VectorStore"]))
test("L2 access_api.retriever",    lambda: __import__("Layer2_Knowledge.access_api.retriever", fromlist=["DiplomaticRetriever"]))
test("L2 access_api.knowledge_api",lambda: __import__("Layer2_Knowledge.access_api.knowledge_api", fromlist=["KnowledgeAPI"]))
test("L2 storage.multi_index",       lambda: __import__("Layer2_Knowledge.storage.multi_index", fromlist=["MultiIndexManager"]))
test("L2 normalization.entity_registry", lambda: __import__("Layer2_Knowledge.normalization.entity_registry", fromlist=["EntityRegistry"]))
test("L2 normalization.source_registry", lambda: __import__("Layer2_Knowledge.normalization.source_registry", fromlist=["SourceRegistry"]))
test("L2 shim retriever",          lambda: __import__("Layer2_Knowledge.retriever", fromlist=["DiplomaticRetriever"]))
test("L2 shim knowledge_api",      lambda: __import__("Layer2_Knowledge.knowledge_api", fromlist=["KnowledgeAPI"]))

# ── Layer 3 (unchanged) ──
test("L3 state_provider",          lambda: __import__("Layer3_StateModel.interface.state_provider", fromlist=["build_initial_state"]))

# ── Layer 4 (renamed subfolders, shims deleted) ──
test("L4 core.coordinator",        lambda: __import__("Layer4_Analysis.core.coordinator", fromlist=["Coordinator"]))
test("L4 core.llm_client",         lambda: __import__("Layer4_Analysis.core.llm_client", fromlist=["llm_client"]))
test("L4 core.council_session",    lambda: __import__("Layer4_Analysis.core.council_session", fromlist=["CouncilSession"]))
test("L4 intake.question_scope",   lambda: __import__("Layer4_Analysis.intake.question_scope_checker", fromlist=["check_question_scope"]))
test("L4 hypothesis.mcts",         lambda: __import__("Layer4_Analysis.hypothesis.mcts", fromlist=["MCTSRAGAgent"]))
test("L4 deliberation.cove",         lambda: __import__("Layer4_Analysis.deliberation.cove", fromlist=["cove_verifier"]))
test("L4 deliberation.red_team",   lambda: __import__("Layer4_Analysis.deliberation.red_team", fromlist=["RedTeamAgent"]))
test("L4 decision.refusal_engine", lambda: __import__("Layer4_Analysis.decision.refusal_engine", fromlist=["refusal_engine"]))
test("L4 investigation.controller",lambda: __import__("Layer4_Analysis.investigation.investigation_controller", fromlist=["InvestigationController"]))

# ── API + Pipeline ──
test("Config.pipeline",            lambda: __import__("Config.pipeline", fromlist=["initialize", "run_query"]))
test("API.main",                   lambda: __import__("API.main", fromlist=["app"]))

out.write(f"\n{'='*40}\n")
out.write(f"TOTAL: {passed + failed}  PASSED: {passed}  FAILED: {failed}\n")
out.close()
print(f"Done: {passed}/{passed+failed} passed")
