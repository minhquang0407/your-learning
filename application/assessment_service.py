"""Quiz generation and grading use cases."""
from typing import Any
from application.contracts import GradeQuizRequest, GradingView, QuizRequest, QuizView
from application.exceptions import OperationFailedError, ValidationError

class AssessmentService:
    """Typed application boundary over RuntimeEngine assessment operations."""
    def __init__(self, runtime_engine: Any): self.runtime_engine = runtime_engine

    def generate_quiz(self, request: QuizRequest) -> QuizView:
        if not request.target_file.strip() or not request.target_section.strip():
            raise ValidationError("Quiz generation requires a target file and section.")
        try:
            questions, error = self.runtime_engine.get_lesson_quiz(request.target_file, request.target_section)
        except Exception as exc:
            raise OperationFailedError("The quiz could not be generated.") from exc
        return QuizView(questions=list(questions or []), error=error)

    def grade_quiz(self, request: GradeQuizRequest) -> GradingView:
        if not request.quiz: raise ValidationError("A quiz is required for grading.")
        try:
            raw = self.runtime_engine.grade_lesson_quiz(request.quiz, request.answers, user_id=request.user_id)
        except Exception as exc:
            raise OperationFailedError("The quiz could not be graded.") from exc
        result = raw.get("grading_result", raw) if isinstance(raw, dict) else {}
        return GradingView(
            score=float(result.get("score", 0.0) or 0.0),
            correct=int(result.get("correct_count", 0) or 0),
            total=int(result.get("total_count", len(request.quiz)) or 0),
            details=list(result.get("details", []) or []),
        )
