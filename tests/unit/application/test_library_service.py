import pytest

from application.exceptions import ValidationError
from application.library_service import LibraryService


class FakeVectorStore:
    def __init__(self): self.calls = []
    def list_sources(self): return ["a.md", "b.md"]
    def get_section_questions(self, parent_id): return [f"question:{parent_id}"]
    def delete_source(self, name): self.calls.append(("delete_source", name))
    def delete_user_history(self, user_id): self.calls.append(("delete_user_history", user_id))


class FakeGraphStore:
    def __init__(self): self.calls = []
    def get_table_of_contents(self, name): return {"Chapter": ["Section"]}
    def get_file_learning_progress(self, user_id, name): return {"total": 4, "learned": 1, "percent": 25}
    def get_global_visual_graph(self, user_id, name): return {"nodes": [{"id": "A"}], "edges": []}
    def get_chapter_visual_graph(self, user_id, name, chapter): return {"nodes": [{"id": chapter}], "edges": []}
    def get_history_by_section(self, user_id, name, section, limit=50): return [{"query": "q", "answer": "a"}]
    def mark_concept_as_learned(self, concept, user): self.calls.append(("learn", concept, user))
    def delete_source(self, name): self.calls.append(("delete_source", name))
    def delete_table_of_contents(self, name): self.calls.append(("delete_toc", name))
    def reset_user_data(self, user): self.calls.append(("reset_user", user))


@pytest.fixture
def service(): return LibraryService(FakeVectorStore(), FakeGraphStore())


def test_library_read_models(service):
    assert [d.file_name for d in service.list_documents()] == ["a.md", "b.md"]
    assert service.get_curriculum("a.md").table_of_contents["Chapter"] == ["Section"]
    assert service.get_progress("u", "a.md").percent == 25
    assert service.get_graph("u", "a.md").nodes[0]["id"] == "A"
    assert service.get_graph("u", "a.md", "C").nodes[0]["id"] == "C"
    assert service.get_section_history("u", "a.md", "S")[0].answer == "a"
    assert service.get_section_questions("p") == ["question:p"]


def test_library_commands_delegate(service):
    service.mark_concept_learned("u", "A")
    service.delete_document("a.md")
    service.reset_user("u")
    assert ("learn", "A", "u") in service.graph_store.calls
    assert ("delete_toc", "a.md") in service.graph_store.calls
    assert ("delete_user_history", "u") in service.vector_store.calls


@pytest.mark.parametrize("operation", [
    lambda s: s.get_curriculum(""), lambda s: s.get_progress("u", " "),
    lambda s: s.get_section_questions(""), lambda s: s.reset_user(""),
])
def test_invalid_identifiers_raise(service, operation):
    with pytest.raises(ValidationError): operation(service)
