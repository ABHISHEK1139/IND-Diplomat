"""Example WebSocket client to subscribe to job updates.

Usage:
  python tools/ws_client.py <job_id>

Requires: `websockets` (pip install websockets)
"""
import asyncio
import sys
import json

import websockets


async def run(job_id: str, url: str = "ws://localhost:8000/ws/assessments"):
    async with websockets.connect(url) as ws:
        # wait for connected message
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            print("RECV:", msg)
        except asyncio.TimeoutError:
            pass

        # subscribe to job topic
        subscribe = {"action": "subscribe", "topic": f"job:{job_id}"}
        await ws.send(json.dumps(subscribe))
        print(f"Subscribed to job:{job_id}")

        while True:
            try:
                data = await ws.recv()
                try:
                    parsed = json.loads(data)
                    print("MSG:", json.dumps(parsed, indent=2))
                except Exception:
                    print("MSG RAW:", data)
            except websockets.ConnectionClosed:
                print("Connection closed")
                return


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/ws_client.py <job_id>")
        sys.exit(1)
    job = sys.argv[1]
    asyncio.run(run(job))
