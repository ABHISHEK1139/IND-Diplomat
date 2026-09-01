"""Simple worker that polls the job store and dispatches queued jobs.
This is a lightweight worker for environments without an external queue.
"""
import asyncio
import time
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dip.api.analyst.job_store import STORE, run_job_background


async def poll_loop(poll_interval: int = 5):
    while True:
        jobs = await STORE.list_jobs(limit=200)
        for job in jobs:
            if job.get("status") == "QUEUED":
                job_id = job["job_id"]
                # mark started and run in background
                await STORE.update_job(job_id, status="RUNNING", started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                asyncio.create_task(run_job_background(job_id, job.get("query", ""), job.get("country", "IND")))
        await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    try:
        asyncio.run(poll_loop())
    except KeyboardInterrupt:
        print("worker stopped")
