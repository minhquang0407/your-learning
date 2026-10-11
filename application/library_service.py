"""Document library, curriculum, progress, history, and graph use cases."""

from typing import Any

from application.contracts import (
    ChatTurnView,
    CurriculumView,
    DocumentSummary,
    KnowledgeGraphView,
    LearningProgress,
)
from application.exceptions import ValidationError
from application.mappers import map_chat_history, map_knowledge_graph, map_learning_progress


class LibraryService:
    """Framework-neutral boundary for document and learner-library operations."""

    def __init__(self, vector_store: Any, graph_store: Any):
        self.vector_store = vector_store
        self.graph_store = graph_store

    def list_documents(self) -> list[DocumentSummary]:
        return [DocumentSummary(file_name=name) for name in self.vector_store.list_sources()]

    def get_curriculum(self, file_name: str) -> CurriculumView:
        self._require_file_name(file_name)
        toc = self.graph_store.get_table_of_contents(file_name) or {}
        return CurriculumView(file_name=file_name, table_of_contents=toc)

    def get_progress(self, user_id: str, file_name: str) -> LearningProgress:
        self._require_file_name(file_name)
        return map_learning_progress(self.graph_store.get_file_learning_progress(user_id, file_name))

    def get_graph(
        self,
        user_id: str,
        file_name: str,
        chapter_name: str | None = None,
    ) -> KnowledgeGraphView:
        self._require_file_name(file_name)
        raw = (
            self.graph_store.get_chapter_visual_graph(user_id, file_name, chapter_name)
            if chapter_name
            else self.graph_store.get_global_visual_graph(user_id, file_name)
        )
        return map_knowledge_graph(raw)

    def get_section_history(
        self,
        user_id: str,
        file_name: str,
        section_name: str,
        limit: int = 50,
    ) -> list[ChatTurnView]:
        self._require_file_name(file_name)
        if not section_name.strip():
            raise ValidationError("Section name is required.")
        return map_chat_history(
            self.graph_store.get_history_by_section(user_id, file_name, section_name, limit=limit)
        )

    def get_section_questions(self, parent_id: str) -> list[str]:
        if not parent_id.strip():
            raise ValidationError("Parent section ID is required.")
        return self.vector_store.get_section_questions(parent_id)

    def mark_concept_learned(self, user_id: str, concept_id: str) -> None:
        if not concept_id.strip():
            raise ValidationError("Concept ID is required.")
        self.graph_store.mark_concept_as_learned(concept_id, user_id)

    def delete_document(self, file_name: str) -> None:
        self._require_file_name(file_name)
        self.vector_store.delete_source(file_name)
        self.graph_store.delete_source(file_name)
        self.graph_store.delete_table_of_contents(file_name)

    def reset_user(self, user_id: str) -> None:
        if not user_id.strip():
            raise ValidationError("User ID is required.")
        self.vector_store.delete_user_history(user_id)
        self.graph_store.reset_user_data(user_id)

    @staticmethod
    def _require_file_name(file_name: str) -> None:
        if not file_name.strip():
            raise ValidationError("File name is required.")

