from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol
from urllib import error, request
from urllib.parse import urlencode

from .exceptions import (
    AuthenticationError,
    ContextGraphConnectionError,
    NotFoundError,
    PermissionDeniedError,
    ServerError,
    ValidationError,
)

if TYPE_CHECKING:
    from ._local import LocalTransport as LocalTransport


class Transport(Protocol):
    def register_agent(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def update_agent_defaults(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get_agent(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def update_agent_profile(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def discover_agents(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def agent_activity(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def store(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def store_async(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def update_memory_access(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def recall(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
    def relate(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
    def watch(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def list_watches(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
    def deactivate_watch(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def job_status(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def list_jobs(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
    def list_claims(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
    def notifications(self, agent_id: str) -> list[dict[str, Any]]: ...
    def review_claim(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def review_queue(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
    def operator_summary(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def expire_claims(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def suspend_agent(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def reactivate_agent(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def delete_agent(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def sentinel_verdicts(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
    def sentinel_health(self, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(slots=True)
class HttpTransport:
    base_url: str
    api_key: str | None = None

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url.rstrip('/')}{path}"
        data = None
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Agent-Key"] = self.api_key
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req) as response:  # noqa: S310 - caller controls base_url
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = self._parse_error_detail(exc)
            raise self._map_http_error(exc.code, detail) from exc
        except error.URLError as exc:
            raise ContextGraphConnectionError(str(exc.reason)) from exc

    def _parse_error_detail(self, exc: error.HTTPError) -> str:
        body = exc.read().decode("utf-8", errors="replace")
        if not body:
            return exc.reason
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return body
        if isinstance(payload, dict):
            if "detail" in payload:
                return str(payload["detail"])
            error_payload = payload.get("error")
            if isinstance(error_payload, dict) and "message" in error_payload:
                return str(error_payload["message"])
        return body

    def _map_http_error(self, status_code: int, detail: str) -> Exception:
        if status_code == 400:
            return ValidationError(detail, status_code)
        if status_code == 401:
            return AuthenticationError(detail, status_code)
        if status_code == 403:
            return PermissionDeniedError(detail, status_code)
        if status_code == 404:
            return NotFoundError(detail, status_code)
        return ServerError(detail, status_code)

    def register_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/agents/register", payload)

    def update_agent_defaults(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = payload["agent_id"]
        body = {
            key: value
            for key, value in payload.items()
            if key in {"default_visibility", "default_access_list", "default_price"} and value is not None
        }
        return self._request("PATCH", f"/v1/agents/{agent_id}/defaults", body)

    def get_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", f"/v1/agents/{payload['agent_id']}")

    def update_agent_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = payload["agent_id"]
        body = {
            key: value
            for key, value in payload.items()
            if key in {"profile_visibility", "profile_access_list", "profile_summary", "profile_links"}
            and value is not None
        }
        return self._request("PATCH", f"/v1/agents/{agent_id}/profile", body)

    def discover_agents(self, payload: dict[str, Any]) -> dict[str, Any]:
        query_params = {
            key: value
            for key, value in payload.items()
            if key in {"q", "status", "min_reputation", "org_id", "visibility", "sort_by", "limit", "offset"}
            and value is not None
            and value != ""
        }
        path = "/v1/agents/discover"
        if query_params:
            path = f"{path}?{urlencode(query_params)}"
        return self._request("GET", path)

    def agent_activity(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = payload["agent_id"]
        query_params = {
            key: value
            for key, value in payload.items()
            if key in {"limit", "offset"} and value is not None
        }
        path = f"/v1/agents/{agent_id}/activity"
        if query_params:
            path = f"{path}?{urlencode(query_params)}"
        return self._request("GET", path)

    def store(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/memory/store", payload)

    def store_async(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/memory/store-async", payload)

    def update_memory_access(self, payload: dict[str, Any]) -> dict[str, Any]:
        memory_id = payload["memory_id"]
        body = {
            key: value
            for key, value in payload.items()
            if key in {"visibility", "price", "access_list"} and value is not None
        }
        return self._request("PATCH", f"/v1/memories/{memory_id}/access", body)

    def recall(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return self._request("POST", "/v1/memory/recall", payload)

    def relate(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return self._request("POST", "/v1/memory/relate", payload)

    def watch(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/watch", payload)

    def list_watches(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        path = "/v1/watch"
        if payload.get("include_inactive"):
            path = "/v1/watch?include_inactive=true"
        return self._request("GET", path)

    def deactivate_watch(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/v1/watch/{payload['query_id']}/deactivate")

    def job_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", f"/v1/jobs/{payload['job_id']}")

    def list_jobs(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/jobs")

    def list_claims(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        query_params: dict[str, Any] = {}
        if payload.get("validation_status") is not None:
            query_params["validation_status"] = payload["validation_status"]
        if payload.get("only_needing_review"):
            query_params["only_needing_review"] = "true"
        if payload.get("limit") is not None:
            query_params["limit"] = payload["limit"]
        path = "/v1/claims"
        if query_params:
            path = f"{path}?{urlencode(query_params)}"
        return self._request("GET", path)

    def notifications(self, agent_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/v1/notifications/{agent_id}")

    def review_claim(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/claims/review", payload)

    def review_queue(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/review-queue")

    def operator_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", "/v1/operator/summary")

    def expire_claims(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/maintenance/claims/expire")

    def suspend_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = payload["agent_id"]
        body = {"reason": payload.get("reason", "manual")}
        return self._request("POST", f"/v1/agents/{agent_id}/suspend", body)

    def reactivate_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = payload["agent_id"]
        return self._request("POST", f"/v1/agents/{agent_id}/reactivate")

    def delete_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = payload["agent_id"]
        return self._request("DELETE", f"/v1/agents/{agent_id}")

    def sentinel_verdicts(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        params = {}
        if payload.get("claim_id"):
            params["claim_id"] = payload["claim_id"]
        if payload.get("decision"):
            params["decision"] = payload["decision"]
        path = "/v1/audit/verdicts"
        if params:
            path = f"{path}?{urlencode(params)}"
        return self._request("GET", path)

    def sentinel_health(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", "/v1/sentinel/health")


class ContextGraph:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    @classmethod
    def local(cls, service: Any | None = None) -> ContextGraph:
        try:
            from ._local import LocalTransport
        except ImportError as exc:
            raise ImportError(
                "LocalTransport requires the full contextgraph server package. "
                "Install it with: pip install contextgraph-sdk[local] or pip install contextgraph"
            ) from exc
        if service is None:
            from contextgraph.service import ContextGraphService

            service = ContextGraphService()
        return cls(LocalTransport(service))

    @classmethod
    def http(cls, base_url: str, api_key: str | None = None) -> ContextGraph:
        return cls(HttpTransport(base_url=base_url, api_key=api_key))

    def register_agent(
        self,
        name: str,
        org_id: str,
        capabilities: list[str] | None = None,
        default_visibility: str | None = None,
        default_access_list: list[str] | None = None,
        default_price: float | None = None,
    ) -> dict[str, Any]:
        return self.transport.register_agent(
            {
                "name": name,
                "org_id": org_id,
                "capabilities": capabilities or [],
                "default_visibility": default_visibility,
                "default_access_list": default_access_list,
                "default_price": default_price,
            }
        )

    def update_agent_defaults(
        self,
        agent_id: str,
        default_visibility: str | None = None,
        default_access_list: list[str] | None = None,
        default_price: float | None = None,
    ) -> dict[str, Any]:
        return self.transport.update_agent_defaults(
            {
                "agent_id": agent_id,
                "default_visibility": default_visibility,
                "default_access_list": default_access_list,
                "default_price": default_price,
            }
        )

    def agent(self, requester_agent_id: str, agent_id: str) -> dict[str, Any]:
        return self.transport.get_agent({"requester_agent_id": requester_agent_id, "agent_id": agent_id})

    def update_agent_profile(
        self,
        requester_agent_id: str,
        agent_id: str,
        profile_visibility: str | None = None,
        profile_access_list: list[str] | None = None,
        profile_summary: str | None = None,
        profile_links: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self.transport.update_agent_profile(
            {
                "requester_agent_id": requester_agent_id,
                "agent_id": agent_id,
                "profile_visibility": profile_visibility,
                "profile_access_list": profile_access_list,
                "profile_summary": profile_summary,
                "profile_links": profile_links,
            }
        )

    def discover(
        self,
        requester_agent_id: str,
        q: str = "",
        status: str | None = None,
        min_reputation: float = 0.0,
        org_id: str | None = None,
        visibility: str | None = None,
        sort_by: str = "reputation",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self.transport.discover_agents(
            {
                "requester_agent_id": requester_agent_id,
                "q": q,
                "status": status,
                "min_reputation": min_reputation,
                "org_id": org_id,
                "visibility": visibility,
                "sort_by": sort_by,
                "limit": limit,
                "offset": offset,
            }
        )

    def agent_activity(
        self,
        requester_agent_id: str,
        agent_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self.transport.agent_activity(
            {
                "requester_agent_id": requester_agent_id,
                "agent_id": agent_id,
                "limit": limit,
                "offset": offset,
            }
        )

    def store(
        self,
        agent_id: str,
        content: str,
        visibility: str | None = None,
        license: str = "internal",
        metadata: dict[str, str] | None = None,
        evidence: list[str] | None = None,
        citations: list[str] | None = None,
        access_list: list[str] | None = None,
        price: float | None = None,
        expires_in_days: int | None = None,
    ) -> dict[str, Any]:
        return self.transport.store(
            {
                "agent_id": agent_id,
                "content": content,
                "visibility": visibility,
                "license": license,
                "metadata": metadata or {},
                "evidence": evidence,
                "citations": citations,
                "access_list": access_list,
                "price": price,
                "expires_in_days": expires_in_days,
            }
        )

    def store_async(
        self,
        agent_id: str,
        content: str,
        visibility: str | None = None,
        license: str = "internal",
        metadata: dict[str, str] | None = None,
        evidence: list[str] | None = None,
        citations: list[str] | None = None,
        access_list: list[str] | None = None,
        price: float | None = None,
        expires_in_days: int | None = None,
    ) -> dict[str, Any]:
        return self.transport.store_async(
            {
                "agent_id": agent_id,
                "content": content,
                "visibility": visibility,
                "license": license,
                "metadata": metadata or {},
                "evidence": evidence,
                "citations": citations,
                "access_list": access_list,
                "price": price,
                "expires_in_days": expires_in_days,
            }
        )

    def update_memory_access(
        self,
        requester_agent_id: str,
        memory_id: str,
        visibility: str | None = None,
        price: float | None = None,
        access_list: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.transport.update_memory_access(
            {
                "requester_agent_id": requester_agent_id,
                "memory_id": memory_id,
                "visibility": visibility,
                "price": price,
                "access_list": access_list,
            }
        )

    def recall(self, agent_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return self.transport.recall({"agent_id": agent_id, "query": query, "limit": limit})

    def relate(self, agent_id: str, entity_a: str, entity_b: str, max_depth: int = 2) -> list[dict[str, Any]]:
        return self.transport.relate(
            {
                "agent_id": agent_id,
                "entity_a": entity_a,
                "entity_b": entity_b,
                "max_depth": max_depth,
            }
        )

    def watch(
        self,
        agent_id: str,
        query: str,
        name: str | None = None,
        delivery_mode: str = "pull",
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self.transport.watch(
            {
                "agent_id": agent_id,
                "query": query,
                "name": name,
                "delivery_mode": delivery_mode,
                "filters": filters or {},
            }
        )

    def watches(self, requester_agent_id: str, include_inactive: bool = False) -> list[dict[str, Any]]:
        return self.transport.list_watches(
            {
                "requester_agent_id": requester_agent_id,
                "include_inactive": include_inactive,
            }
        )

    def deactivate_watch(self, requester_agent_id: str, query_id: str) -> dict[str, Any]:
        return self.transport.deactivate_watch(
            {
                "requester_agent_id": requester_agent_id,
                "query_id": query_id,
            }
        )

    def job_status(self, job_id: str, requester_agent_id: str) -> dict[str, Any]:
        return self.transport.job_status(
            {
                "job_id": job_id,
                "requester_agent_id": requester_agent_id,
            }
        )

    def notifications(self, agent_id: str) -> list[dict[str, Any]]:
        return self.transport.notifications(agent_id)

    def jobs(self, requester_agent_id: str) -> list[dict[str, Any]]:
        return self.transport.list_jobs({"requester_agent_id": requester_agent_id})

    def claims(
        self,
        requester_agent_id: str,
        validation_status: str | None = None,
        only_needing_review: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.transport.list_claims(
            {
                "requester_agent_id": requester_agent_id,
                "validation_status": validation_status,
                "only_needing_review": only_needing_review,
                "limit": limit,
            }
        )

    def review_claim(
        self,
        reviewer_agent_id: str,
        claim_id: str,
        decision: str,
        reason: str = "",
    ) -> dict[str, Any]:
        return self.transport.review_claim(
            {
                "reviewer_agent_id": reviewer_agent_id,
                "claim_id": claim_id,
                "decision": decision,
                "reason": reason,
            }
        )

    def review_queue(self, requester_agent_id: str) -> list[dict[str, Any]]:
        return self.transport.review_queue({"requester_agent_id": requester_agent_id})

    def operator_summary(self, requester_agent_id: str) -> dict[str, Any]:
        return self.transport.operator_summary({"requester_agent_id": requester_agent_id})

    def expire_claims(self, requester_agent_id: str) -> dict[str, Any]:
        return self.transport.expire_claims({"requester_agent_id": requester_agent_id})

    def suspend_agent(self, agent_id: str, reason: str = "manual") -> dict[str, Any]:
        return self.transport.suspend_agent({"agent_id": agent_id, "reason": reason})

    def reactivate_agent(self, agent_id: str) -> dict[str, Any]:
        return self.transport.reactivate_agent({"agent_id": agent_id})

    def delete_agent(self, agent_id: str) -> dict[str, Any]:
        return self.transport.delete_agent({"agent_id": agent_id})

    def sentinel_verdicts(self, claim_id: str | None = None, decision: str | None = None) -> list[dict[str, Any]]:
        return self.transport.sentinel_verdicts({"claim_id": claim_id, "decision": decision})

    def sentinel_health(self) -> dict[str, Any]:
        return self.transport.sentinel_health({})
