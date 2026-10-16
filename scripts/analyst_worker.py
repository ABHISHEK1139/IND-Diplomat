"""Simple worker that polls the job store and dispatches queued jobs.
This is a lightweight worker for environments without an external queue.

Claiming is atomic (see ``JobStore.claim_job``): two workers racing on the
same QUEUED job cannot both run it. Concurrency is capped with a semaphore
and every task is tracked so shutdown can cancel cleanly.
"""
import asyncio
import os
import sys

# Anchor the package on sys.path so the script runs from any CWD without
# requiring an installed distribution (pip install -e . also works).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "src")
sys.path.insert(0, _SRC if os.path.isdir(os.path.join(_SRC, "dip")) else _ROOT)

from dip.api.analyst.job_store import STORE, run_job_background

# Max pipeline jobs running concurrently in this worker.
MAX_CONCURRENCY = int(os.getenv("WORKER_MAX_CONCURRENCY", "2"))


async def _run_claimed(semaphore: asyncio.Semaphore, job: dict) -> None:
    job_id = job["job_id"]
    async with semaphore:
        try:
            await run_job_background(job_id, job.get("query", ""), job.get("country", "IND"))
        except asyncio.CancelledError:
            # Cancellation is handled by the caller; the job stays RUNNING and
            # is failed as interrupted on the next startup (mark_interrupted).
            raise
        except Exception as exc:  # noqa: BLE001 - never let a task die silently
            await STORE.update_job(job_id, status="FAILED", error=f"worker runner crashed: {exc}")


async def poll_loop(poll_interval: int = 5):
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    running: set[asyncio.Task] = set()
    while True:
        # Refresh the view each tick; claim_job decides the winner atomically.
        jobs = await STORE.list_jobs(limit=200)
        for job in jobs:
            if job.get("status") != "QUEUED":
                continue
            claimed = await STORE.claim_job(job["job_id"])
            if claimed is None:
                continue  # lost the race to another worker
            task = asyncio.create_task(_run_claimed(semaphore, claimed))
            running.add(task)
            task.add_done_callback(running.discard)
        try:
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            for task in running:
                task.cancel()
            if running:
                await asyncio.gather(*running, return_exceptions=True)
            raise


if __name__ == "__main__":
    try:
        asyncio.run(poll_loop())
    except KeyboardInterrupt:
        print("worker stopped")
