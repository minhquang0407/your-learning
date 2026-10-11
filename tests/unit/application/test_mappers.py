from application.events import EventKind
from application.mappers import map_chat_history, map_knowledge_graph, map_learning_progress, map_runtime_event


def test_runtime_event_preserves_unknown_payload():
    event = map_runtime_event({"type": "token", "content": "abc", "agent": "math", "seq": 2})
    assert event.kind is EventKind.CHUNK
    assert event.agent_name == "math"
    assert event.payload == {"seq": 2}
    assert not event.is_terminal


def test_terminal_event():
    assert map_runtime_event({"type": "final"}).is_terminal
    assert map_runtime_event({"type": "error"}).is_terminal


def test_progress_is_clamped():
    result = map_learning_progress({"total": 2, "learned": 9, "percent": 120})
    assert (result.total, result.learned, result.percent) == (2, 2, 100.0)


def test_graph_and_history_mapping():
    graph = map_knowledge_graph({"nodes": [{"id": "A"}], "edges": []})
    history = map_chat_history([{"query": "q", "answer": "a"}])
    assert graph.nodes[0]["id"] == "A"
    assert history[0].query == "q"
