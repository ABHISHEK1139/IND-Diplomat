"""Debug: why WorldBank/Comtrade sensors fail to load via importlib."""
import sys, os, traceback, importlib.util
from pathlib import Path

proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, proj)

api_dir = Path(proj) / "LAYER1_COLLECTION" / "api"

# WorldBank
wb_path = api_dir / "Eonomic Pressure (World Bank)" / "sensor.py"
print(f"WB path exists: {wb_path.exists()}")
try:
    spec = importlib.util.spec_from_file_location(
        "layer1_wb_sensor", str(wb_path),
        submodule_search_locations=[str(wb_path.parent)]
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print(f"WB OK: {dir(mod)}")
except Exception:
    traceback.print_exc()

print()

# Comtrade
ct_path = api_dir / "Supply Chain Leverage (Comtrade)" / "sensor.py"
print(f"CT path exists: {ct_path.exists()}")
try:
    spec = importlib.util.spec_from_file_location(
        "layer1_ct_sensor", str(ct_path),
        submodule_search_locations=[str(ct_path.parent)]
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print(f"CT OK: {dir(mod)}")
except Exception:
    traceback.print_exc()
