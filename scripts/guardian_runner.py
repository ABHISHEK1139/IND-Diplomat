"""Guardian runner that periodically performs health checks and logs results."""
import time
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dip.SystemGuardian import SystemGuardian, get_guardian


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
