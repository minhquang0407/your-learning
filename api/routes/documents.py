"""Document library and ingestion routes."""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request

from api.dependencies import get_learning_app
from application.contracts import IngestDocumentRequest
from application.exceptions import ResourceNotFoundError, ValidationError
from application.facade import LearningApplication
from database.document_processor import MathAwareDocumentProcessor

router = APIRouter(prefix="/api", tags=["documents"])

MAX_INGEST_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit


@router.get("/documents")
def list_documents(
    facade: LearningApplication = Depends(get_learning_app),
) -> Dict[str, Any]:
    """Return all available documents and their curriculum structure."""
    try:
        raw_docs = (
            facade.library.list_documents()
            if hasattr(facade, "library") and hasattr(facade.library, "list_documents")
            else facade.list_documents()
        )
        documents: List[Dict[str, Any]] = []

        for doc in raw_docs:
            toc = {}
            try:
                curriculum = facade.get_curriculum(doc.file_name)
                toc = curriculum.table_of_contents
            except Exception:
                toc = {}

            documents.append({
                "file_name": doc.file_name,
                "table_of_contents": toc,
            })

        return {"documents": documents}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(exc)}")


@router.get("/documents/{file_name}")
def get_document_details(
    file_name: str,
    user_id: str = "guest_01",
    facade: LearningApplication = Depends(get_learning_app),
) -> Dict[str, Any]:
    """Return curriculum and progress details for a specific document."""
    if not file_name or not file_name.strip():
        raise HTTPException(status_code=400, detail="File name cannot be empty.")
    try:
        curriculum = facade.get_curriculum(file_name)
        progress = facade.get_progress(user_id=user_id, file_name=file_name)
        return {
            "file_name": file_name,
            "table_of_contents": curriculum.table_of_contents,
            "progress": {
                "total": progress.total,
                "learned": progress.learned,
                "percent": progress.percent,
            },
        }
    except ValidationError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except ResourceNotFoundError as not_found:
        raise HTTPException(status_code=404, detail=str(not_found))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Document not found or error loading: {str(exc)}")


@router.post("/ingest")
async def ingest_document(
    request: Request,
    facade: LearningApplication = Depends(get_learning_app),
) -> Dict[str, Any]:
    """Ingest a learning document (via file upload or JSON payload)."""
    content_type = request.headers.get("content-type", "")
    target_name = ""
    target_content = ""

    raw_file_bytes: bytes | None = None
    already_converted = False
    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        if uploaded_file and hasattr(uploaded_file, "read"):
            target_name = getattr(uploaded_file, "filename", "uploaded_doc.md")
            raw_bytes = await uploaded_file.read()
            if len(raw_bytes) > MAX_INGEST_FILE_SIZE:
                raise HTTPException(status_code=413, detail="Document exceeds maximum allowed size of 10MB.")
            raw_file_bytes = raw_bytes
            clean_lower_name = target_name.strip().lower()
            if any(clean_lower_name.endswith(ext) for ext in (".pdf", ".pptx", ".docx")):
                processor = MathAwareDocumentProcessor()
                target_content = processor.convert_to_markdown(file_bytes=raw_bytes, filename=target_name)
                already_converted = True
            else:
                target_content = raw_bytes.decode("utf-8", errors="replace")
        else:
            target_name = str(form.get("file_name", ""))
            target_content = str(form.get("content", ""))
    else:
        try:
            body = await request.json()
            target_name = body.get("file_name", "")
            target_content = body.get("content", "")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON or form payload.")

    if not target_name.strip():
        raise HTTPException(status_code=400, detail="File name cannot be empty.")
    if not target_content.strip():
        raise HTTPException(status_code=400, detail="Document content cannot be empty.")

    # Validate file extension if filename provided
    clean_lower_name = target_name.strip().lower()
    supported_extensions = (".md", ".txt", ".pdf", ".pptx", ".docx")
    if clean_lower_name and not any(clean_lower_name.endswith(ext) for ext in supported_extensions):
        raise HTTPException(
            status_code=400,
            detail="Only Markdown (.md) or text (.txt), PDF (.pdf), PowerPoint (.pptx), or Word (.docx) files are supported.",
        )

    # Convert non-markdown content if sent via JSON payload and preserve raw bytes
    if not already_converted and any(clean_lower_name.endswith(ext) for ext in (".pdf", ".pptx", ".docx")) and target_content:
        import base64
        import os
        if os.path.exists(target_content) and os.path.isfile(target_content):
            try:
                with open(target_content, "rb") as f:
                    raw_file_bytes = f.read()
            except Exception:
                pass
        else:
            clean_str = target_content.strip()
            if clean_str.startswith("data:") and ";base64," in clean_str:
                clean_str = clean_str.split(";base64,")[1]
            try:
                decoded = base64.b64decode(clean_str, validate=True)
                if len(decoded) > 0:
                    raw_file_bytes = decoded
            except Exception:
                pass

        processor = MathAwareDocumentProcessor()
        target_content = processor.convert_to_markdown(content_or_bytes=target_content, file_bytes=raw_file_bytes, filename=target_name)

    if len(target_content.encode("utf-8")) > MAX_INGEST_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Document exceeds maximum allowed size of 10MB.")

    try:
        ingest_req = IngestDocumentRequest(file_name=target_name, content=target_content, file_bytes=raw_file_bytes)
        events = list(facade.ingest(ingest_req))
        errors = [e.message for e in events if e.kind.value == "error"]
        if errors:
            raise HTTPException(status_code=500, detail=f"Ingestion error: {'; '.join(errors)}")

        return {
            "status": "success",
            "file_name": target_name,
            "events_count": len(events),
            "message": f"Successfully ingested {target_name}",
        }
    except HTTPException:
        raise
    except ValidationError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to ingest document: {str(exc)}")


@router.delete("/documents/{file_name}")
def delete_document(
    file_name: str,
    facade: LearningApplication = Depends(get_learning_app),
) -> Dict[str, Any]:
    """Delete a document from vector and graph stores."""
    if not file_name or not file_name.strip():
        raise HTTPException(status_code=400, detail="File name cannot be empty.")
    try:
        facade.delete_document(file_name)
        return {"status": "success", "file_name": file_name, "message": f"Deleted {file_name}"}
    except ValidationError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(exc)}")
