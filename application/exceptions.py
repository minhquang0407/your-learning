"""Application-level exceptions safe for presentation adapters.

TODO:
- Translate database/LLM exceptions into these types inside services.
- Keep raw provider errors in logs; return safe messages to the UI.
"""


class ApplicationError(Exception):
    """Base error for an application use case."""


class ValidationError(ApplicationError):
    """The request cannot be processed because its input is invalid."""


class ResourceNotFoundError(ApplicationError):
    """A requested document, section, lesson, or quiz was not found."""


class DependencyUnavailableError(ApplicationError):
    """A required local service such as Ollama, Qdrant, or Neo4j is unavailable."""


class InvalidModeError(ValidationError):
    """The requested runtime or QA mode is not supported."""


class OperationFailedError(ApplicationError):
    """A use case started but could not complete successfully."""
