import asyncio

from dip.api_ws.ws_manager import manager
from dip.ind_diplomat import diplomat_query


class StubWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


async def _run_and_collect(job_id: str, query: str):
    stub = StubWebSocket()
    conn_id = "test_conn_" + job_id
    manager.active_connections[conn_id] = stub
    await manager.subscribe(conn_id, f"job:{job_id}")

    # run diplomat query (will publish start/completed to job:{job_id})
    await diplomat_query(query, "CXY", job_id=job_id)

    # allow queued publish tasks to run
    await asyncio.sleep(0.5)
    return stub.messages


def test_job_ws_events():
    job_id = "evt123"
    messages = asyncio.run(_run_and_collect(job_id, "test signals for ws"))
    # should receive at least started and completed events
    types = [m.get("type") for m in messages]
    assert "pipeline.started" in types or any(m.get("type") == "phase.started" for m in messages)
    assert "pipeline.completed" in types or any(m.get("type") == "phase.completed" for m in messages)
