"""Document ingestion use case.

Migration TODO:
1. Move orchestration from ``core.data_ingestion.run_ingestion_pipeline`` here.
2. Replace every ``st.status/st.write/st.error`` call with ``ApplicationEvent`` yields.
3. Validate file size, encoding, extension, and duplicate document policy.
4. Add bounded retries per section and report partial failures.
5. Decide whether failed ingestion rolls back or remains resumable.
6. Keep document parsing, LLM extraction, and persistence as injected dependencies.
"""

from collections.abc import Iterable
from typing import Any

from application.contracts import IngestDocumentRequest
from application.events import ApplicationEvent


class IngestionService:
    def __init__(self, vector_store: Any, graph_store: Any, llm_service: Any, document_processor: Any):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.llm_service = llm_service
        self.document_processor = document_processor

    def ingest(self, request: IngestDocumentRequest) -> Iterable[ApplicationEvent]:
        """Ingest one document while reporting framework-neutral progress events."""
        # TODO: Port the current pipeline incrementally and add tests before switching the UI.
        raise NotImplementedError("TODO: implement IngestionService.ingest")
