from __future__ import annotations

from .config import Settings, settings
from .graph.neo4j_repository import Neo4jRepository
from .in_memory import InMemoryRepository
from .service import ContextGraphService


def create_repository(app_settings: Settings | None = None):
    current = app_settings or settings
    backend = current.repository_backend.strip().lower()
    if backend == "memory":
        return InMemoryRepository()
    if backend == "neo4j":
        return Neo4jRepository(
            uri=current.neo4j_uri,
            user=current.neo4j_user,
            password=current.neo4j_password,
        )
    raise RuntimeError(f"Unsupported repository backend '{current.repository_backend}'.")


def create_service(app_settings: Settings | None = None) -> ContextGraphService:
    current = app_settings or settings
    return ContextGraphService(repository=create_repository(current), app_settings=current)

