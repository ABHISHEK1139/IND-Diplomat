"""
IND-Diplomat Analyst Workstation — Combined Launcher
=====================================================
Starts both the Analyst API (port 8100) and the Frontend UI server (port 3000).

Usage:
    python -m analyst_api.launch
"""

import multiprocessing
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def run_analyst_api():
    """Start the Analyst API on port 8100."""
    os.chdir(str(_ROOT))
    import uvicorn
    from analyst_api.main import app
    uvicorn.run(app, host="0.0.0.0", port=8100, log_level="info")


def run_frontend():
    """Start the Frontend UI server on port 3000."""
    os.chdir(str(_ROOT))
    import uvicorn
    from Frontend.server import app
    uvicorn.run(app, host="0.0.0.0", port=3000, log_level="info")


def main():
    print("=" * 60)
    print("  IND-Diplomat — Analyst Workstation Launcher")
    print("=" * 60)
    print()
    print("  Dashboard:   http://localhost:3000")
    print("  Analyst API: http://localhost:8100/docs")
    print("  API Proxy:   http://localhost:3000/api/v3/*")
    print()
    print("=" * 60)
    print()

    # Start both servers
    api_proc = multiprocessing.Process(target=run_analyst_api, daemon=True)
    ui_proc = multiprocessing.Process(target=run_frontend, daemon=True)

    api_proc.start()
    ui_proc.start()

    try:
        api_proc.join()
        ui_proc.join()
    except KeyboardInterrupt:
        print("\nShutting down…")
        api_proc.terminate()
        ui_proc.terminate()


if __name__ == "__main__":
    main()
