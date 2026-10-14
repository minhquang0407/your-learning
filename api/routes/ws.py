"""WebSocket endpoint for real-time telemetry and streaming."""

import json
import logging
import time
from typing import Any, Dict
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from api.dependencies import get_learning_app
from application.contracts import LessonRequest, QuestionRequest
from application.facade import LearningApplication

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["websocket"])


class ConnectionManager:
    """Manages active WebSocket sessions."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str) -> None:
        self.active_connections.pop(session_id, None)

    async def send_json(self, session_id: str, data: Dict[str, Any]) -> None:
        ws = self.active_connections.get(session_id)
        if ws:
            await ws.send_json(data)


manager = ConnectionManager()


@router.websocket("/ws/session/{session_id}")
async def websocket_session_endpoint(
    websocket: WebSocket,
    session_id: str,
    facade: LearningApplication = Depends(get_learning_app),
):
    """Bi-directional WebSocket channel for telemetry and tutoring interactions."""
    await manager.connect(session_id, websocket)

    # Handshake confirmation
    await websocket.send_json({
        "type": "CONNECTED",
        "session_id": session_id,
        "payload": {
            "status": "ready",
            "timestamp": time.time(),
            "message": "AI Cognitive Tutor session connected",
        },
    })

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except Exception:
                data = {"type": "RAW_TEXT", "payload": {"text": raw_data}}

            msg_type = data.get("type", "UNKNOWN")
            payload = data.get("payload", {})

            # 1. Telemetry: Learner is idle
            if msg_type == "PING_IDLE":
                idle_seconds = payload.get("idleSeconds", 20)
                await websocket.send_json({
                    "type": "PROACTIVE_NUDGE",
                    "session_id": session_id,
                    "payload": {
                        "message": "Thầy thấy em đang suy nghĩ ở phần này. Em có muốn gợi ý về công thức hoặc tương tác thử với mô phỏng không?",
                        "idleSeconds": idle_seconds,
                        "suggestions": [
                            "Giải thích trực quan F = m*a",
                            "Thử kéo góc nghiêng alpha",
                            "Tóm tắt ý chính của phần này",
                        ],
                    },
                })

            # 2. Telemetry: Widget state changed on Main Canvas
            elif msg_type == "WIDGET_CHANGE":
                widget_id = payload.get("widget_id", "simulation")
                values = payload.get("values", {})
                await websocket.send_json({
                    "type": "WIDGET_FEEDBACK",
                    "session_id": session_id,
                    "payload": {
                        "status": "acknowledged",
                        "widget_id": widget_id,
                        "echo": values,
                        "hint": f"Đã ghi nhận thay đổi thông số mô phỏng ({widget_id}).",
                    },
                })

            # 3. Telemetry: Video player seek / timeupdate
            elif msg_type == "VIDEO_SEEK":
                current_time = payload.get("currentTime", 0.0)
                await websocket.send_json({
                    "type": "SYNC_ACK",
                    "session_id": session_id,
                    "payload": {
                        "currentTime": current_time,
                        "synced": True,
                    },
                })

            # 4. User question through WebSocket
            elif msg_type in ("USER_QUESTION", "CHAT_QUERY"):
                query = payload.get("query", "").strip()
                if not query:
                    await websocket.send_json({
                        "type": "ERROR",
                        "session_id": session_id,
                        "payload": {"error": "Query cannot be empty"},
                    })
                    continue

                try:
                    req = QuestionRequest(
                        user_id=payload.get("user_id", "guest_01"),
                        query=query,
                        mode=payload.get("mode", "GLOBAL_QA"),
                        target_file=payload.get("target_file", ""),
                        target_section=payload.get("target_section", ""),
                    )
                    from starlette.concurrency import run_in_threadpool
                    answer = await run_in_threadpool(facade.ask, req)
                    await websocket.send_json({
                        "type": "CHAT_RESPONSE",
                        "session_id": session_id,
                        "payload": {
                            "content": answer.content,
                            "metadata": answer.metadata,
                        },
                    })
                except Exception as ask_err:
                    await websocket.send_json({
                        "type": "ERROR",
                        "session_id": session_id,
                        "payload": {"error": f"Failed to process question: {str(ask_err)}"},
                    })

            # 5. Stream Lesson
            elif msg_type == "STREAM_LESSON":
                try:
                    step_data = payload.get("step_data") or {"step_title": payload.get("target_section", "Introduction")}
                    req = LessonRequest(
                        user_id=payload.get("user_id", "guest_01"),
                        target_file=payload.get("target_file", ""),
                        target_section=payload.get("target_section", ""),
                        step_data=step_data,
                    )
                    from starlette.concurrency import run_in_threadpool
                    events = await run_in_threadpool(lambda: list(facade.stream_lesson(req)))
                    for event in events:
                        await websocket.send_json({
                            "type": "LESSON_EVENT",
                            "session_id": session_id,
                            "payload": {
                                "kind": event.kind.value,
                                "content": event.content,
                                "message": event.message,
                                "payload": event.payload,
                            },
                        })
                except Exception as lesson_err:
                    await websocket.send_json({
                        "type": "ERROR",
                        "session_id": session_id,
                        "payload": {"error": f"Failed to stream lesson: {str(lesson_err)}"},
                    })

            # 6. Default ACK
            else:
                await websocket.send_json({
                    "type": "ACK",
                    "session_id": session_id,
                    "payload": {
                        "received_type": msg_type,
                        "timestamp": time.time(),
                    },
                })

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info(f"WebSocket session disconnected: {session_id}")
    except Exception as exc:
        manager.disconnect(session_id)
        logger.error(f"WebSocket error in session {session_id}: {exc}")
