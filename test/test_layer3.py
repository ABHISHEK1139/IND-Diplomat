"""Phase 4: Layer 3 State Model Verification."""
import sys, os, traceback
proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, proj)

from test._support import script_log_path

out = open(script_log_path("layer3_results.log"), "w", encoding="utf-8")

# 1. StateContext round-trip
out.write("=== 1. StateContext ===\n")
try:
    from engine.Layer3_StateModel.schemas.state_context import StateContext
    sc = StateContext(country_code="IND")
    d = sc.to_dict()
    out.write(f"OK: StateContext created, keys={list(d.keys())[:8]}\n")
    out.write(f"  query={d.get('query')}, country={d.get('country_code')}\n")
    out.write(f"  data_quality={d.get('data_quality')}\n")
except Exception:
    out.write("FAIL:\n")
    traceback.print_exc(file=out)

# 2. KnowledgePort
out.write("\n=== 2. KnowledgePort ===\n")
try:
    from Core.orchestrator.knowledge_port import knowledge_port
    out.write(f"OK: knowledge_port type={type(knowledge_port).__name__}\n")
    out.write(f"  methods: {[m for m in dir(knowledge_port) if not m.startswith('_')][:10]}\n")
except Exception:
    out.write("FAIL:\n")
    traceback.print_exc(file=out)

# 3. state_provider — build_initial_state
out.write("\n=== 3. build_initial_state ===\n")
try:
    from engine.Layer3_StateModel.interface.state_provider import build_initial_state
    state = build_initial_state("India Pakistan trade relations", country_code="IND")
    out.write(f"OK: type={type(state).__name__}\n")
    if hasattr(state, 'to_dict'):
        d = state.to_dict()
        out.write(f"  keys: {list(d.keys())[:8]}\n")
        out.write(f"  data_quality={d.get('data_quality')}\n")
        signals = d.get('signals', [])
        out.write(f"  signals_count={len(signals)}\n")
    else:
        out.write(f"  type={type(state)}, value={str(state)[:200]}\n")
except Exception:
    out.write("FAIL:\n")
    traceback.print_exc(file=out)

# 4. investigate_and_update
out.write("\n=== 4. investigate_and_update ===\n")
try:
    from engine.Layer3_StateModel.interface.state_provider import investigate_and_update
    out.write(f"OK: function loaded, type={type(investigate_and_update).__name__}\n")
    # Don't call it — just confirm it exists
except Exception:
    out.write("FAIL:\n")
    traceback.print_exc(file=out)

# 5. Analysis readiness
out.write("\n=== 5. evaluate_analysis_readiness ===\n")
try:
    from engine.Layer3_StateModel.construction.analysis_readiness import evaluate_analysis_readiness
    out.write(f"OK: function loaded\n")
except Exception:
    out.write("FAIL:\n")
    traceback.print_exc(file=out)

# 6. CountryStateBuilder
out.write("\n=== 6. CountryStateBuilder ===\n")
try:
    from engine.Layer3_StateModel.construction.country_state_builder import CountryStateBuilder
    csb = CountryStateBuilder()
    out.write(f"OK: CountryStateBuilder created, type={type(csb).__name__}\n")
    out.write(f"  methods: {[m for m in dir(csb) if not m.startswith('_')][:10]}\n")
except Exception:
    out.write("FAIL:\n")
    traceback.print_exc(file=out)

out.close()
print("Done")
