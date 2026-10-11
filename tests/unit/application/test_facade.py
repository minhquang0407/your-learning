import pytest
from unittest.mock import MagicMock
from application.facade import LearningApplication
from application.contracts import (
    AnswerResult,
    DocumentSummary,
    GradingView,
    GradeQuizRequest,
    LessonRequest,
    QuestionRequest,
    QuizRequest,
    QuizView,
    SourceBriefingView,
)
from application.events import ApplicationEvent, EventKind
from agents.critic_agent import CriticAgent
from core.schemas import AgentMessage, AgentTask, BlackboardState
import core.schemas as schemas


def test_facade_delegates_to_services():
    ingestion = MagicMock()
    learning = MagicMock()
    qa = MagicMock()
    assessment = MagicMock()
    library = MagicMock()
    briefing = MagicMock()

    app = LearningApplication(
        ingestion=ingestion,
        learning=learning,
        qa=qa,
        assessment=assessment,
        library=library,
        briefing=briefing,
    )

    # 1. Ask
    qa.ask.return_value = AnswerResult(content="Academic answer")
    ask_req = QuestionRequest(user_id="u", query="q", mode="GLOBAL_QA")
    assert app.ask(ask_req).content == "Academic answer"
    qa.ask.assert_called_once_with(ask_req)

    # 2. Stream lesson
    learning.stream_lesson.return_value = [ApplicationEvent(kind=EventKind.CHUNK, content="part")]
    lesson_req = LessonRequest(user_id="u", target_file="f", target_section="s", step_data={"step_id": "1"})
    events = list(app.stream_lesson(lesson_req))
    assert len(events) == 1 and events[0].content == "part"
    learning.stream_lesson.assert_called_once_with(lesson_req)

    # 3. Generate quiz
    assessment.generate_quiz.return_value = QuizView(questions=[{"question": "What is X?"}])
    quiz_req = QuizRequest(user_id="u", target_file="f", target_section="s")
    assert len(app.generate_quiz(quiz_req).questions) == 1
    assessment.generate_quiz.assert_called_once_with(quiz_req)

    # 4. Grade quiz
    assessment.grade_quiz.return_value = GradingView(score=1.0, correct=1, total=1)
    grade_req = GradeQuizRequest(user_id="u", quiz=[{"question": "What is X?"}], answers={"0": 0})
    assert app.grade_quiz(grade_req).score == 1.0
    assessment.grade_quiz.assert_called_once_with(grade_req)

    # 5. Generate briefing
    briefing.generate.return_value = SourceBriefingView(synopsis="synopsis", key_themes=["t1"])
    assert app.generate_briefing("file.md").synopsis == "synopsis"
    briefing.generate.assert_called_once_with("file.md")

    # 6. List documents
    library.list_documents.return_value = [DocumentSummary(file_name="book.md")]
    assert len(app.list_documents()) == 1
    library.list_documents.assert_called_once()

    # 7. Library delegations
    app.get_curriculum("book.md")
    library.get_curriculum.assert_called_once_with("book.md")

    app.get_progress("u", "book.md")
    library.get_progress.assert_called_once_with("u", "book.md")

    app.get_graph("u", "book.md", "c1")
    library.get_graph.assert_called_once_with("u", "book.md", "c1")

    app.get_section_history("u", "book.md", "s1")
    library.get_section_history.assert_called_once_with("u", "book.md", "s1", limit=50)

    app.get_section_questions("p1")
    library.get_section_questions.assert_called_once_with("p1")

    app.mark_concept_learned("u", "c1")
    library.mark_concept_learned.assert_called_once_with("u", "c1")

    app.delete_document("book.md")
    library.delete_document.assert_called_once_with("book.md")

    app.reset_user("u")
    library.reset_user.assert_called_once_with("u")


def test_critic_agent_marks_failed_agent_as_fail():
    critic = CriticAgent()

    # Variant 1: standard failed message with error metadata
    bb = BlackboardState()
    bb.agent_messages.append(
        AgentMessage(
            agent_name="concept",
            role="Concept Expert",
            content="Agent concept failed: API rate limit exceeded",
            metadata={"error": "Rate limit"},
        )
    )
    task = AgentTask(task_id="critic_step_1", agent_name="critic", instruction="Review concept step")
    result = critic.run(task, bb)
    report = result.message.metadata["critic_report"]
    assert report["status"] == "fail"
    assert "Agent execution failed" in report["issues"][0]
    assert result.message.needs_revision is True

    # Variant 2: failure text without metadata (e.g. specialist or assessment failure)
    bb2 = BlackboardState()
    bb2.agent_messages.append(
        AgentMessage(
            agent_name="math",
            role="Math Expert",
            content="MathAgent failed: Remote disconnected",
        )
    )
    task2 = AgentTask(task_id="critic_step_2", agent_name="critic", instruction="Review math step")
    result2 = critic.run(task2, bb2)
    report2 = result2.message.metadata["critic_report"]
    assert report2["status"] == "fail"
    assert result2.message.needs_revision is True


def test_orchestrator_compat_delegates_to_multi_agent_runtime():
    from runtime.engine import RuntimeEngine
    mock_runtime = MagicMock()
    mock_llm = MagicMock()
    engine = RuntimeEngine(multi_agent_runtime=mock_runtime, llm_service=mock_llm)

    assert engine.orchestrator.llm_service is mock_llm
    step = {"step_id": "1", "step_title": "Vectors", "main_entities": ["Vector"]}
    engine.orchestrator.execute_teaching_step(step_data=step, macro_context="Vector text", user_id="u1")
    mock_runtime.execute_learning.assert_called_once_with(
        user_id="u1",
        target_file="",
        target_section="Vectors",
        step_data=step,
        macro_context="Vector text",
        anchor_nodes=["Vector"],
    )


def test_schemas_clean_without_legacy_models():
    assert not hasattr(schemas, "AgentClaim")
    assert not hasattr(schemas, "QueueState")
    msg = AgentMessage(
        agent_name="concept",
        role="Concept Expert",
        content="Intro to vectors",
        claims=["vectors have magnitude and direction"],
    )
    assert msg.claims == ["vectors have magnitude and direction"]
