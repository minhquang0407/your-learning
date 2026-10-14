"""Dependency providers for FastAPI routes."""

from functools import lru_cache
from typing import Optional

from application.facade import LearningApplication
from config.settings import settings
from core.container import Container
from runtime.engine import RuntimeEngine


_container_instance: Optional[Container] = None


def get_container() -> Container:
    """Return initialized Container singleton."""
    global _container_instance
    if _container_instance is None:
        container = Container()
        container.config.from_pydantic(settings)
        _container_instance = container
    return _container_instance


def set_container(container: Optional[Container]) -> None:
    """Explicitly set or reset container instance (useful for testing)."""
    global _container_instance
    _container_instance = container


def get_learning_app() -> LearningApplication:
    """Provide LearningApplication instance."""
    container = get_container()
    return container.learning_application()


def get_runtime_engine() -> RuntimeEngine:
    """Provide RuntimeEngine instance."""
    container = get_container()
    return container.runtime_engine()
