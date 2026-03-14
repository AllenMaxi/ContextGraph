from __future__ import annotations

from .config import settings

try:
    import uvicorn
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    uvicorn = None


def run() -> None:
    if uvicorn is None:  # pragma: no cover - optional dependency
        raise RuntimeError('uvicorn is not installed. Install with `pip install -e ".[server]"`.')
    uvicorn.run(
        "contextgraph.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
