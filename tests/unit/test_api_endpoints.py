"""Unit tests for FastAPI endpoints (REST and WebSocket)."""

from unittest.mock import MagicMock
import pytest
from starlette.testclient import TestClient

from api.app import create_app
from api.dependencies import get_learning_app, get_runtime_engine
from application.contracts import (
    AnswerResult,
    CurriculumView,
    DocumentSummary,
    LearningProgress,
    QuestionRequest,
)
from application.events import ApplicationEvent, EventKind


@pytest.fixture
def mock_facade():
    facade = MagicMock()
    # Mock list_documents & get_curriculum
    facade.list_documents.return_value = [DocumentSummary(file_name="newton_laws.md")]
    facade.library.list_documents.return_value = [DocumentSummary(file_name="newton_laws.md")]
    facade.get_curriculum.return_value = CurriculumView(
        file_name="newton_laws.md",
        table_of_contents={"Chương 1: Cơ học cổ điển": ["Định luật 2 Newton", "Lực ma sát"]},
    )
    facade.get_progress.return_value = LearningProgress(total=10, learned=5, percent=50.0)
    # Mock ask
    facade.ask.return_value = AnswerResult(
        content="Theo định luật 2 Newton, F = m * a.",
        metadata={"mode": "GLOBAL_QA", "sources": ["newton_laws.md"]},
    )
    # Mock ingest
    facade.ingest.return_value = [
        ApplicationEvent(kind=EventKind.STATUS, message="Analyzing"),
        ApplicationEvent(kind=EventKind.FINAL, message="Done", payload={"sections": 2}),
    ]
    # Mock stream_lesson
    facade.stream_lesson.return_value = [
        ApplicationEvent(kind=EventKind.STATUS, message="Starting step"),
        ApplicationEvent(kind=EventKind.CHUNK, content="Step 1 explanation"),
        ApplicationEvent(kind=EventKind.FINAL, message="Step complete"),
    ]
    return facade


@pytest.fixture
def mock_runtime_engine():
    engine = MagicMock()
    # Mock Qdrant
    engine.vector_db.client.get_collections.return_value = []
    # Mock Neo4j
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = False
    mock_session.run.return_value = [{"1": 1}]
    engine.graph_db.driver.session.return_value = mock_session
    # Mock LLM
    mock_response = MagicMock()
    mock_response.content = "OK"
    engine.llm_service.chat_llm.invoke.return_value = mock_response
    return engine


@pytest.fixture
def client(mock_facade, mock_runtime_engine):
    app = create_app()
    app.dependency_overrides[get_learning_app] = lambda: mock_facade
    app.dependency_overrides[get_runtime_engine] = lambda: mock_runtime_engine
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_health_check_healthy(client, mock_runtime_engine):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["components"]["qdrant"]["status"] == "connected"
    assert data["components"]["neo4j"]["status"] == "connected"
    assert data["components"]["llm"]["status"] == "connected"


def test_health_check_degraded_when_neo4j_fails(client, mock_runtime_engine):
    mock_runtime_engine.graph_db.driver.session.side_effect = Exception("Connection refused")
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["components"]["neo4j"]["status"] == "error"
    assert data["components"]["qdrant"]["status"] == "connected"


def test_get_documents(client, mock_facade):
    response = client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert len(data["documents"]) == 1
    doc = data["documents"][0]
    assert doc["file_name"] == "newton_laws.md"
    assert "Chương 1: Cơ học cổ điển" in doc["table_of_contents"]


def test_get_document_details(client, mock_facade):
    response = client.get("/api/documents/newton_laws.md")
    assert response.status_code == 200
    data = response.json()
    assert data["file_name"] == "newton_laws.md"
    assert data["progress"]["percent"] == 50.0


def test_chat_endpoint_success(client, mock_facade):
    payload = {
        "query": "Định luật 2 Newton là gì?",
        "user_id": "student_01",
        "mode": "GLOBAL_QA",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "F = m * a" in data["content"]
    assert data["metadata"]["mode"] == "GLOBAL_QA"
    mock_facade.ask.assert_called_once()


def test_chat_endpoint_validation_empty_query(client):
    response = client.post("/api/chat", json={"query": "  "})
    assert response.status_code == 400


def test_ingest_json_payload(client, mock_facade):
    payload = {
        "file_name": "test_doc.md",
        "content": "# Test Document\n\n## Section 1\nContent here",
    }
    response = client.post("/api/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["file_name"] == "test_doc.md"


def test_ingest_file_upload(client, mock_facade):
    files = {"file": ("uploaded_physics.md", b"# Physics\n\n## Kinematics\nMotion", "text/markdown")}
    response = client.post("/api/ingest", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["file_name"] == "uploaded_physics.md"


def test_ingest_missing_content_error(client):
    response = client.post("/api/ingest", json={"file_name": "", "content": ""})
    assert response.status_code == 400


def test_websocket_telemetry_flow(client):
    with client.websocket_connect("/api/ws/session/test_session_123") as websocket:
        # Handshake confirmation
        handshake = websocket.receive_json()
        assert handshake["type"] == "CONNECTED"
        assert handshake["session_id"] == "test_session_123"

        # 1. PING_IDLE telemetry
        websocket.send_json({"type": "PING_IDLE", "payload": {"idleSeconds": 25}})
        nudge = websocket.receive_json()
        assert nudge["type"] == "PROACTIVE_NUDGE"
        assert "suggestions" in nudge["payload"]

        # 2. WIDGET_CHANGE telemetry
        websocket.send_json({
            "type": "WIDGET_CHANGE",
            "payload": {"widget_id": "angle_slider", "values": {"alpha": 45}},
        })
        feedback = websocket.receive_json()
        assert feedback["type"] == "WIDGET_FEEDBACK"
        assert feedback["payload"]["widget_id"] == "angle_slider"

        # 3. VIDEO_SEEK telemetry
        websocket.send_json({"type": "VIDEO_SEEK", "payload": {"currentTime": 142.5}})
        sync = websocket.receive_json()
        assert sync["type"] == "SYNC_ACK"
        assert sync["payload"]["currentTime"] == 142.5


def test_websocket_user_question_and_streaming(client, mock_facade):
    with client.websocket_connect("/api/ws/session/test_session_456") as websocket:
        # Handshake
        handshake = websocket.receive_json()
        assert handshake["type"] == "CONNECTED"

        # 1. Ask question via WebSocket
        websocket.send_json({
            "type": "USER_QUESTION",
            "payload": {"query": "Giải thích định luật 2 Newton"},
        })
        chat_res = websocket.receive_json()
        assert chat_res["type"] == "CHAT_RESPONSE"
        assert "F = m * a" in chat_res["payload"]["content"]

        # 2. Stream lesson via WebSocket
        websocket.send_json({
            "type": "STREAM_LESSON",
            "payload": {
                "target_file": "newton_laws.md",
                "target_section": "Định luật 2 Newton",
            },
        })
        # Expect multiple LESSON_EVENT messages
        event1 = websocket.receive_json()
        assert event1["type"] == "LESSON_EVENT"
        assert event1["payload"]["kind"] == "status"

        event2 = websocket.receive_json()
        assert event2["type"] == "LESSON_EVENT"
        assert event2["payload"]["kind"] == "chunk"
        assert "Step 1" in event2["payload"]["content"]

        event3 = websocket.receive_json()
        assert event3["type"] == "LESSON_EVENT"
        assert event3["payload"]["kind"] == "final"


def test_websocket_empty_query_error(client):
    with client.websocket_connect("/api/ws/session/test_session_789") as websocket:
        websocket.receive_json()  # Handshake
        websocket.send_json({"type": "USER_QUESTION", "payload": {"query": "   "}})
        err = websocket.receive_json()
        assert err["type"] == "ERROR"
        assert "cannot be empty" in err["payload"]["error"]


def test_chat_endpoint_validation_error(client, mock_facade):
    from application.exceptions import ValidationError
    mock_facade.ask.side_effect = ValidationError("Target section is required.")
    response = client.post("/api/chat", json={"query": "test query", "mode": "LOCAL_QA"})
    assert response.status_code == 400
    assert "Target section is required" in response.json()["detail"]
    mock_facade.ask.side_effect = None


def test_ingest_oversized_file_rejected(client):
    large_content = "A" * (11 * 1024 * 1024)  # 11MB
    response = client.post("/api/ingest", json={"file_name": "large.md", "content": large_content})
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"]


def test_ingest_unsupported_file_extension_rejected(client):
    response = client.post("/api/ingest", json={"file_name": "malicious.exe", "content": "dummy executable code"})
    assert response.status_code == 400
    assert "Only Markdown (.md) or text (.txt)" in response.json()["detail"]


def test_delete_document_success(client, mock_facade):
    response = client.delete("/api/documents/newton_laws.md")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_facade.delete_document.assert_called_with("newton_laws.md")


def test_delete_document_empty_name_error(client):
    response = client.delete("/api/documents/%20")
    assert response.status_code == 400
