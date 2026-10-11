"""Source-level briefing use case."""
from typing import Any
from application.contracts import SourceBriefingView
from application.exceptions import OperationFailedError, ValidationError

class BriefingService:
    def __init__(self, runtime_engine: Any): self.runtime_engine = runtime_engine

    def generate(self, file_name: str) -> SourceBriefingView:
        if not file_name.strip(): raise ValidationError("File name is required.")
        try: raw, error = self.runtime_engine.get_source_briefing(file_name)
        except Exception as exc: raise OperationFailedError("The source briefing could not be generated.") from exc
        raw = raw or {}
        return SourceBriefingView(
            synopsis=str(raw.get("synopsis", "")),
            key_themes=list(raw.get("key_themes", []) or []),
            podcast_script=str(raw.get("podcast_script", "")), error=error,
        )
