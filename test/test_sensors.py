"""Verify all 3 sensors produce live data."""
import sys, os
proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, proj)

from test._support import script_log_path

out = open(script_log_path("sensor_results.log"), "w", encoding="utf-8")

from engine.Layer1_Collection import GDELTSensor, WorldBankSensor, ComtradeSensor

# GDELT
out.write("=== GDELT ===\n")
try:
    g = GDELTSensor()
    state = g.get_state(["IND", "CHN"], hours_back=24)
    out.write(f"OK: events={state.get('event_count',0)}, tension={state.get('tension_level','?')}\n")
except Exception as e:
    out.write(f"FAIL: {e}\n")

# WorldBank
out.write("\n=== WorldBank ===\n")
try:
    wb = WorldBankSensor()
    state = wb.get_state("IND", years_back=5)
    out.write(f"OK: status={state.get('status')}, pressure={state.get('economic_pressure')}\n")
    out.write(f"  vulnerability={state.get('vulnerability_score')}\n")
    inds = state.get('indicators', {})
    out.write(f"  indicators: {list(inds.keys())[:5]}\n")
    gdp = inds.get('gdp', {})
    out.write(f"  GDP: ${gdp.get('value', 0):,.0f} ({gdp.get('year', '?')})\n")
except Exception as e:
    out.write(f"FAIL: {e}\n")

# Comtrade
out.write("\n=== Comtrade ===\n")
try:
    ct = ComtradeSensor()
    state = ct.get_state(reporter="IND", partner="CHN")
    out.write(f"OK: status={state.get('status')}\n")
    out.write(f"  keys: {list(state.keys())[:8]}\n")
except Exception as e:
    out.write(f"FAIL: {e}\n")

out.close()
print("Done")
