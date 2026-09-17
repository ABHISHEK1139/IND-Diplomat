"""Guardian runner that periodically performs health checks and logs results."""
import time
import asyncio
import os
import sys

# Anchor the package on sys.path so the script runs from any CWD without
# requiring an installed distribution (pip install -e . also works).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "src")
sys.path.insert(0, _SRC if os.path.isdir(os.path.join(_SRC, "dip")) else _ROOT)

from dip.engines.SystemGuardian import SystemGuardian, get_guardian


async def loop(interval: int = 60):
    guardian = get_guardian()
    while True:
        report = guardian.full_health_report()
        print("[guardian] health:", report.get("healthy"), "| checks:", list(report.get("checks", {}).keys()))
        await asyncio.sleep(interval)


if __name__ == "__main__":
    try:
        asyncio.run(loop())
    except KeyboardInterrupt:
        print("guardian stopped")
