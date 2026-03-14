from __future__ import annotations

import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any

from .api._compat import FastAPI, JSONResponse
from .api.console import register_console_routes
from .api.routes import register_routes
from .bootstrap import create_service
from .config import settings
from .errors import AuthenticationError, ContextGraphError, NotFoundError, PaymentRequiredError, PermissionDeniedError
from .service import ContextGraphService


def create_app(service: ContextGraphService | None = None) -> Any:
    if FastAPI is None:  # pragma: no cover - optional dependency
        raise RuntimeError('FastAPI is not installed. Install with `pip install -e ".[server]"`.')

    graph = service or create_service()

    @asynccontextmanager
    async def lifespan(_: Any):
        try:
            yield
        finally:
            graph.close()

    app = FastAPI(title="ContextGraph", version="0.2.0", lifespan=lifespan)

    # --- CORS middleware ---
    try:
        from starlette.middleware.cors import CORSMiddleware

        origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    except ImportError:  # pragma: no cover
        pass

    # --- Simple rate limiting middleware ---
    _rate_buckets: dict[str, list[float]] = defaultdict(list)
    _rate_limit = settings.rate_limit_per_minute

    @app.middleware("http")
    async def rate_limit_middleware(request: Any, call_next: Any) -> Any:
        api_key = request.headers.get("x-agent-key", request.client.host if request.client else "unknown")
        now = time.monotonic()
        window = _rate_buckets[api_key]
        # Prune entries older than 60s
        cutoff = now - 60
        _rate_buckets[api_key] = [t for t in window if t > cutoff]
        if len(_rate_buckets[api_key]) >= _rate_limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )
        _rate_buckets[api_key].append(now)
        return await call_next(request)

    # --- Body size limit middleware ---
    @app.middleware("http")
    async def body_size_limit_middleware(request: Any, call_next: Any) -> Any:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 1_048_576:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large. Maximum size is 1MB."},
            )
        return await call_next(request)

    register_routes(app, graph)
    register_console_routes(app, graph)

    @app.exception_handler(ContextGraphError)
    async def handle_contextgraph_error(_, exc: ContextGraphError) -> Any:
        status = 400
        if isinstance(exc, AuthenticationError):
            status = 401
        elif isinstance(exc, PaymentRequiredError):
            status = 402
        elif isinstance(exc, NotFoundError):
            status = 404
        elif isinstance(exc, PermissionDeniedError):
            status = 403
        return JSONResponse(status_code=status, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def handle_value_error(_, exc: ValueError) -> Any:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app
