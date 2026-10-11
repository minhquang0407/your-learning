"""Local and global question-answering use cases."""

from typing import Any

from application.contracts import AnswerResult, QuestionRequest
from application.exceptions import InvalidModeError, OperationFailedError, ValidationError


class QAService:
    """Validate and delegate QA requests to the existing runtime engine."""

    ALLOWED_MODES = {"LOCAL_QA", "GLOBAL_QA"}

    def __init__(self, runtime_engine: Any):
        self.runtime_engine = runtime_engine

    def ask(self, request: QuestionRequest) -> AnswerResult:
        mode = request.mode.strip().upper()
        if mode not in self.ALLOWED_MODES:
            raise InvalidModeError(f"Unsupported QA mode: {request.mode}")
        if not request.query.strip():
            raise ValidationError("Question cannot be empty.")
        if mode == "LOCAL_QA" and (not request.target_file.strip() or not request.target_section.strip()):
            raise ValidationError("Local QA requires a target file and section.")

        try:
            raw = self.runtime_engine.process_action(
                action_mode=mode,
                query=request.query,
                target_file=request.target_file,
                target_section=request.target_section,
                user_id=request.user_id,
            )
        except Exception as exc:
            raise OperationFailedError("The question could not be answered.") from exc

        if isinstance(raw, AnswerResult):
            return raw
        if isinstance(raw, dict):
            content = str(raw.get("content", raw.get("answer", "")))
            metadata = {key: value for key, value in raw.items() if key not in {"content", "answer"}}
            return AnswerResult(content=content, metadata=metadata)
        return AnswerResult(content=str(raw))
