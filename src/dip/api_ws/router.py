"""WebSocket router exposing `/ws/assessments` for live updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Any
from .ws_manager import manager
from dip.layer8_collaboration.collaboration.yjs_sync import yjs_engine

router = APIRouter()


@router.websocket("/ws/assessments")
async def websocket_assessments(websocket: WebSocket):
    conn_id = await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "connected", "conn_id": conn_id})
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "subscribe":
                topic = data.get("topic")
                if topic:
                    await manager.subscribe(conn_id, topic)
                    await websocket.send_json({"type": "subscribed", "topic": topic})
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(conn_id)
    except Exception:
        manager.disconnect(conn_id)

@router.websocket("/ws/collab/{document_id}")
async def websocket_collab(websocket: WebSocket, document_id: str):
    """Real-time Yjs CRDT synchronization endpoint for collaborative editing."""
    conn_id = await manager.connect(websocket)
    topic = f"collab_{document_id}"
    await manager.subscribe(conn_id, topic)
    
    # Send the current full state to the newly connected client
    try:
        # Note: In a real app, the client would send its state vector first, 
        # but for simplicity we push the full state on connect.
        update = yjs_engine.encode_state_as_update(document_id)
        if update:
            await websocket.send_bytes(update)
            
        while True:
            # Yjs clients send binary updates (deltas)
            data = await websocket.receive_bytes()
            
            # Apply to server in-memory model
            yjs_engine.apply_update(document_id, data)
            
            # Broadcast delta to other clients in this room to sync them
            await manager.publish_topic_bytes(topic, data, exclude_conn_id=conn_id)
            
    except WebSocketDisconnect:
        manager.disconnect(conn_id)
    except Exception as e:
        manager.disconnect(conn_id)
