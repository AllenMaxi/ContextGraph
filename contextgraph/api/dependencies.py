from __future__ import annotations

from typing import Any

from ..errors import AuthenticationError, PermissionDeniedError
from ..service import ContextGraphService
from ._compat import Header, HTTPException


def build_authenticated_agent_dependency(graph: ContextGraphService):
    def authenticated_agent(x_agent_key: str | None = Header(default=None, alias="X-Agent-Key")) -> Any:
        if not x_agent_key:
            raise HTTPException(status_code=401, detail="Missing X-Agent-Key header.")
        try:
            return graph.authenticate_agent(x_agent_key)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    return authenticated_agent


def require_same_agent(authenticated: Any, claimed_agent_id: str | None, detail: str) -> Any:
    if claimed_agent_id is not None and claimed_agent_id != authenticated.agent_id:
        raise HTTPException(status_code=403, detail=detail)
    return authenticated
