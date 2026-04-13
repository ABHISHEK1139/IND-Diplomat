"""Phase 6: Test API/main.py loads correctly."""
import sys, os, traceback
proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, proj)

from test._support import script_log_path

out = open(script_log_path("api_load.log"), "w", encoding="utf-8")

try:
    from API.main import app
    out.write(f"OK: FastAPI app loaded\n")
    out.write(f"  title={app.title}\n")
    out.write(f"  version={app.version}\n")
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    out.write(f"  routes: {routes}\n")
except Exception:
    out.write("FAIL:\n")
    traceback.print_exc(file=out)

out.close()
print("Done")
