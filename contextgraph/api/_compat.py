from __future__ import annotations

from typing import Any

try:
    from fastapi import Depends, FastAPI, Form, Header, HTTPException, Query, Request
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    from pydantic import BaseModel, ConfigDict, Field
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    FastAPI = None
    Depends = None
    Form = None
    Header = None
    HTTPException = Exception
    HTMLResponse = None
    JSONResponse = None
    Query = None
    RedirectResponse = None
    Request = Any

    class BaseModel:  # pragma: no cover - optional dependency
        pass

    class ConfigDict(dict):  # pragma: no cover - optional dependency
        pass

    def Field(default: Any = None, **_: Any) -> Any:  # pragma: no cover - optional dependency
        return default

__all__ = [
    "BaseModel",
    "ConfigDict",
    "Depends",
    "FastAPI",
    "Field",
    "Form",
    "Header",
    "HTMLResponse",
    "HTTPException",
    "JSONResponse",
    "Query",
    "RedirectResponse",
    "Request",
]
