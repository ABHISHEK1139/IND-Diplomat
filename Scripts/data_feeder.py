"""
Lightweight data feeder runner.
Fetches configured sources (see Layer1_Collection/sources.yaml),
performs deduplication, archives raw HTML, and reports new documents.

Usage:
    cd IND-Dip
    python Scripts/data_feeder.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from feeder.scheduler import ingestion_scheduler


async def main() -> None:
    results = await ingestion_scheduler.run_all_sources(priority_filter=2)

    print("\n=== Data Feeder Run Summary ===")
    for r in results:
        status = "OK" if r.success else "FAIL"
        err = "; ".join(r.errors) if r.errors else "none"
        print(f"{status} {r.source_name}: new={r.new_documents}, total={r.documents_found}, errors={err}")
    print("================================\n")


if __name__ == "__main__":
    asyncio.run(main())
