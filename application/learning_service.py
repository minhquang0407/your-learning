"""Lesson delivery use case."""

from collections.abc import Iterable, Mapping
from typing import Any

from application.contracts import LessonRequest
from application.events import ApplicationEvent, EventKind
from application.exceptions import ValidationError
from application.mappers import map_runtime_event


class LearningService:
    """Typed event-stream boundary over the current learning runtime."""

    def __init__(self, runtime_engine: Any):
        self.runtime_engine = runtime_engine

    def stream_lesson(self, request: LessonRequest) -> Iterable[ApplicationEvent]:
        if not request.target_file.strip() or not request.target_section.strip():
            raise ValidationError("Lesson delivery requires a target file and section.")
        if not request.step_data:
            raise ValidationError("Lesson step data is required.")

        try:
            stream = self.runtime_engine.process_action(
                action_mode="LEARNING",
                target_file=request.target_file,
                target_section=request.target_section,
                step_data=request.step_data,
                user_id=request.user_id,
            )
            for raw in stream:
                if isinstance(raw, ApplicationEvent):
                    yield raw
                elif isinstance(raw, Mapping):
                    yield map_runtime_event(raw)
                else:
                    yield ApplicationEvent(kind=EventKind.CHUNK, content=str(raw))
        except Exception as exc:
            yield ApplicationEvent(
                kind=EventKind.ERROR,
                message="The lesson could not be completed.",
                payload={"exception_type": type(exc).__name__},
            )
