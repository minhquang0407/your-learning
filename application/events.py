"""Framework-neutral progress events emitted by long-running use cases.

TODO:
- Map existing runtime dictionaries to these events at the application boundary.
- Do not put Streamlit rendering instructions into event payloads.
- Add correlation/run IDs when concurrent local jobs are introduced.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventKind(str, Enum):
    STATUS = "status"
    AGENT_START = "agent_start"
    CHUNK = "chunk"
    AGENT_END = "agent_end"
    FINAL = "final"
    ERROR = "error"
    TRACE = "trace"


@dataclass(frozen=True)
class ApplicationEvent:
    kind: EventKind
    message: str = ""
    content: str = ""
    agent_name: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """Return whether consumers must stop reading the current operation."""
        return self.kind in {EventKind.FINAL, EventKind.ERROR}
