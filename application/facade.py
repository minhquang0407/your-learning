"""Single application facade consumed by Streamlit, CLI, or a future local UI.

TODO migration order:
1. Construct this facade in ``core.container.Container``.
2. Change one Streamlit feature at a time to call the facade.
3. After all direct engine/database access is removed, delete obsolete UI logic.
4. Keep this facade free from rendering, HTTP, WebSocket, and session-state concerns.
"""

from collections.abc import Iterable

from application.assessment_service import AssessmentService
from application.briefing_service import BriefingService
from application.contracts import (
    AnswerResult,
    ChatTurnView,
    CurriculumView,
    DocumentSummary,
    GradeQuizRequest,
    GradingView,
    KnowledgeGraphView,
    LearningProgress,
    LessonRequest,
    QuestionRequest,
    QuizRequest,
    QuizView,
    SourceBriefingView,
)
from application.events import ApplicationEvent
from application.ingestion_service import IngestionService
from application.learning_service import LearningService
from application.library_service import LibraryService
from application.qa_service import QAService


class LearningApplication:
    """Groups framework-neutral use cases without implementing transport logic."""

    def __init__(
        self,
        *,
        ingestion: IngestionService,
        learning: LearningService,
        qa: QAService,
        assessment: AssessmentService,
        library: LibraryService,
        briefing: BriefingService,
    ):
        self.ingestion = ingestion
        self.learning = learning
        self.qa = qa
        self.assessment = assessment
        self.library = library
        self.briefing = briefing

    def ask(self, request: QuestionRequest) -> AnswerResult:
        return self.qa.ask(request)

    def stream_lesson(self, request: LessonRequest) -> Iterable[ApplicationEvent]:
        return self.learning.stream_lesson(request)

    def generate_quiz(self, request: QuizRequest) -> QuizView:
        return self.assessment.generate_quiz(request)

    def grade_quiz(self, request: GradeQuizRequest) -> GradingView:
        return self.assessment.grade_quiz(request)

    def generate_briefing(self, file_name: str) -> SourceBriefingView:
        return self.briefing.generate(file_name)

    def list_documents(self) -> list[DocumentSummary]:
        return self.library.list_documents()

    def get_curriculum(self, file_name: str) -> CurriculumView:
        return self.library.get_curriculum(file_name)

    def get_progress(self, user_id: str, file_name: str) -> LearningProgress:
        return self.library.get_progress(user_id, file_name)

    def get_graph(
        self,
        user_id: str,
        file_name: str,
        chapter_name: str | None = None,
    ) -> KnowledgeGraphView:
        return self.library.get_graph(user_id, file_name, chapter_name)

    def get_section_history(
        self,
        user_id: str,
        file_name: str,
        section_name: str,
        limit: int = 50,
    ) -> list[ChatTurnView]:
        return self.library.get_section_history(user_id, file_name, section_name, limit=limit)

    def get_section_questions(self, parent_id: str) -> list[str]:
        return self.library.get_section_questions(parent_id)

    def mark_concept_learned(self, user_id: str, concept_id: str) -> None:
        self.library.mark_concept_learned(user_id, concept_id)

    def delete_document(self, file_name: str) -> None:
        self.library.delete_document(file_name)

    def reset_user(self, user_id: str) -> None:
        self.library.reset_user(user_id)
