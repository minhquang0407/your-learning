import hashlib
from collections.abc import Iterable
from typing import Any, Optional

from application.contracts import IngestDocumentRequest
from application.events import ApplicationEvent, EventKind
from database.entity_resolver import AnchorEntityResolver


class IngestionService:
    def __init__(
        self,
        vector_store: Any,
        graph_store: Any,
        llm_service: Any,
        document_processor: Any,
        entity_resolver: Optional[Any] = None,
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.llm_service = llm_service
        self.document_processor = document_processor
        self.entity_resolver = entity_resolver or AnchorEntityResolver(
            vector_store=vector_store,
            graph_store=graph_store,
            llm_service=llm_service,
        )

    def ingest(self, request: IngestDocumentRequest) -> Iterable[ApplicationEvent]:
        """Ingest one document while reporting framework-neutral progress events."""
        if not request.file_name or not request.file_name.strip():
            yield ApplicationEvent(kind=EventKind.ERROR, message="Document file_name is required")
            return

        if not request.content or not request.content.strip():
            yield ApplicationEvent(kind=EventKind.ERROR, message="Document content cannot be empty")
            return

        try:
            yield ApplicationEvent(
                kind=EventKind.STATUS,
                message=f"Analyzing document structure: {request.file_name}",
            )
            if hasattr(self.document_processor, "process_document"):
                final_document, toc_tree = self.document_processor.process_document(
                    content=request.content,
                    filename=request.file_name,
                    file_bytes=getattr(request, "file_bytes", None),
                )
            else:
                clean_content = (
                    self.document_processor.convert_to_markdown(request.content, filename=request.file_name)
                    if hasattr(self.document_processor, "convert_to_markdown")
                    else request.content
                )
                final_document, toc_tree = self.document_processor.process_markdown(clean_content)

            yield ApplicationEvent(
                kind=EventKind.STATUS,
                message=f"Saving Table of Contents for {request.file_name}",
            )
            self.graph_store.save_table_of_contents(request.file_name, toc_tree)

            global_nodes_list: list[str] = []
            total_sections = len(final_document)

            for i, section in enumerate(final_document):
                sec_name = section.get("metadata", {}).get("Section", "Unknown")
                chapter_name = section.get("metadata", {}).get("Chapter", "Unknown")
                full_section_text = section.get("page_content", "")
                parent_id = hashlib.md5(f"{request.file_name}__{chapter_name}__{sec_name}".encode("utf-8")).hexdigest()

                yield ApplicationEvent(
                    kind=EventKind.STATUS,
                    message=f"Processing section {i+1}/{total_sections}: {sec_name}",
                )

                llm_data = self.llm_service.extract_section_curriculum_and_dag(
                    full_section_text, existing_nodes=global_nodes_list
                )

                main_entities = llm_data.get("main_entities", [])
                teaching_roadmap = llm_data.get("teaching_roadmap", [])
                kg_data = llm_data.get("knowledge_graph", {})
                edges = kg_data.get("edges", [])
                nodes = kg_data.get("nodes", [])

                # Anchor Entity Resolution & Disambiguation
                if self.entity_resolver:
                    resolved_nodes, resolved_edges, name_map = self.entity_resolver.resolve_section_entities(
                        nodes=nodes,
                        edges=edges,
                        source_locator=f"{request.file_name}::{chapter_name}::{sec_name}",
                    )
                    nodes = resolved_nodes
                    edges = resolved_edges
                    main_entities = [name_map.get(m, m) for m in main_entities if m]

                for node in nodes:
                    node_name = node.get("canonical_name") or node.get("name", "").strip()
                    if node_name and node_name not in global_nodes_list:
                        global_nodes_list.append(node_name)

                section_anchors = set()
                for node in nodes:
                    n_id = node.get("canonical_name") or node.get("name")
                    if n_id:
                        section_anchors.add(n_id)
                for e in edges:
                    if "source" in e:
                        section_anchors.add(e["source"])
                    if "target" in e:
                        section_anchors.add(e["target"])

                if nodes or edges:
                    self.graph_store.save_knowledge_graph(
                        nodes=nodes,
                        edges=edges,
                        file_name=request.file_name,
                        chapter_name=chapter_name,
                        section_title=sec_name,
                        main_entities=main_entities,
                    )

                for idx, step_data in enumerate(teaching_roadmap):
                    step_data["seq_id"] = idx
                    self.vector_store.upsert_curriculum_group(
                        group_data=step_data,
                        parent_id=parent_id,
                        source_file=request.file_name,
                        chapter=chapter_name,
                        section=sec_name,
                    )

                questions = self.llm_service.generate_hypothetical_questions(
                    full_section_text, num_questions=5
                )

                parent_metadata = {
                    "source": request.file_name,
                    "section": sec_name,
                    "seq_id": section.get("metadata", {}).get("seq_id", i),
                    "anchor_nodes": ", ".join(list(section_anchors)),
                    "main_entities": ", ".join(main_entities),
                }

                self.vector_store.upsert_section(full_section_text, parent_metadata, parent_id)
                self.vector_store.upsert_questions(questions, parent_id, request.file_name)

                yield ApplicationEvent(
                    kind=EventKind.CHUNK,
                    content=f"Processed section: {sec_name}",
                    payload={"section": sec_name, "chapter": chapter_name, "index": i + 1, "total": total_sections},
                )

            yield ApplicationEvent(
                kind=EventKind.FINAL,
                message=f"Successfully ingested {request.file_name}",
                payload={"file_name": request.file_name, "sections": total_sections},
            )

        except Exception as exc:
            yield ApplicationEvent(
                kind=EventKind.ERROR,
                message=f"Ingestion failed for {request.file_name}: {str(exc)}",
                payload={"error": str(exc)},
            )
