"""Typed requests and responses shared by every presentation adapter.

These contracts intentionally contain no Streamlit, database, or LangChain types.
They form the stable boundary between presentation code and use-case services.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IngestDocumentRequest:
    content: str
    file_name: str
    user_id: str = "local_user"


@dataclass(frozen=True)
class LessonRequest:
    user_id: str
    target_file: str
    target_section: str
    step_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QuestionRequest:
    user_id: str
    query: str
    mode: str
    target_file: str = ""
    target_section: str = ""


@dataclass(frozen=True)
class QuizRequest:
    user_id: str
    target_file: str
    target_section: str


@dataclass(frozen=True)
class GradeQuizRequest:
    user_id: str
    quiz: list[dict[str, Any]]
    answers: dict[str, int]


@dataclass(frozen=True)
class AnswerResult:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentSummary:
    file_name: str


@dataclass(frozen=True)
class CurriculumView:
    file_name: str
    table_of_contents: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class LearningProgress:
    total: int = 0
    learned: int = 0
    percent: float = 0.0


@dataclass(frozen=True)
class KnowledgeGraphView:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ChatTurnView:
    query: str
    answer: str


@dataclass(frozen=True)
class QuizView:
    questions: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class GradingView:
    score: float
    correct: int
    total: int
    details: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SourceBriefingView:
    synopsis: str = ""
    key_themes: list[str] = field(default_factory=list)
    podcast_script: str = ""
    error: str | None = None

