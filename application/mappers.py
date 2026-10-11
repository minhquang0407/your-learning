"""Conversions from infrastructure/runtime dictionaries to application contracts."""
from typing import Any, Mapping
from application.contracts import ChatTurnView, KnowledgeGraphView, LearningProgress
from application.events import ApplicationEvent, EventKind

_EVENT_ALIASES = {
    "status": EventKind.STATUS, "agent_start": EventKind.AGENT_START,
    "token": EventKind.CHUNK, "chunk": EventKind.CHUNK,
    "agent_end": EventKind.AGENT_END, "final": EventKind.FINAL,
    "error": EventKind.ERROR, "trace": EventKind.TRACE,
}

def map_runtime_event(raw: Mapping[str, Any]) -> ApplicationEvent:
    """Normalize one legacy runtime event while preserving unknown fields."""
    raw_type = str(raw.get("type", raw.get("event", "status"))).lower()
    known = {"type", "event", "message", "content", "agent", "agent_name"}
    return ApplicationEvent(
        kind=_EVENT_ALIASES.get(raw_type, EventKind.STATUS),
        message=str(raw.get("message", "")), content=str(raw.get("content", "")),
        agent_name=raw.get("agent_name", raw.get("agent")),
        payload={key: value for key, value in raw.items() if key not in known},
    )

def map_learning_progress(raw: Mapping[str, Any] | None) -> LearningProgress:
    """Normalize graph progress data and clamp invalid values."""
    data = raw or {}; total = max(0, int(data.get("total", 0) or 0))
    learned = max(0, min(total, int(data.get("learned", 0) or 0)))
    percent = max(0.0, min(100.0, float(data.get("percent", 0.0) or 0.0)))
    return LearningProgress(total=total, learned=learned, percent=percent)

def map_knowledge_graph(raw: Mapping[str, Any] | None) -> KnowledgeGraphView:
    """Normalize visual graph output into an immutable application view."""
    data = raw or {}
    return KnowledgeGraphView(nodes=list(data.get("nodes", []) or []), edges=list(data.get("edges", []) or []))

def map_chat_history(raw: list[Mapping[str, Any]] | None) -> list[ChatTurnView]:
    """Normalize section history records."""
    return [ChatTurnView(query=str(x.get("query", "")), answer=str(x.get("answer", ""))) for x in (raw or [])]
