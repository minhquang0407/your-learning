"""Chat and Socratic Q&A route."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_learning_app
from application.contracts import QuestionRequest
from application.exceptions import InvalidModeError, ValidationError
from application.facade import LearningApplication

router = APIRouter(prefix="/api", tags=["chat"])


class ChatPayload(BaseModel):
    query: str = Field(..., description="The user's question or prompt")
    user_id: str = Field(default="guest_01", description="User or session identifier")
    mode: str = Field(default="GLOBAL_QA", description="QA mode: GLOBAL_QA, LOCAL_QA, or LEARNING")
    target_file: Optional[str] = Field(default="", description="Target source document if relevant")
    target_section: Optional[str] = Field(default="", description="Target curriculum section if relevant")


@router.post("/chat")
def chat(
    payload: ChatPayload,
    facade: LearningApplication = Depends(get_learning_app),
) -> Dict[str, Any]:
    """Process user prompt and return Socratic answer with grounding metadata."""
    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        request = QuestionRequest(
            user_id=payload.user_id,
            query=payload.query.strip(),
            mode=payload.mode,
            target_file=payload.target_file or "",
            target_section=payload.target_section or "",
        )
        answer = facade.ask(request)

        return {
            "content": answer.content,
            "metadata": answer.metadata,
        }
    except (ValueError, ValidationError, InvalidModeError) as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"QA failed: {str(exc)}")
