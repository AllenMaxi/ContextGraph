from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import error, request
from urllib.parse import urlencode

from contextgraph.service import ContextGraphService
from contextgraph.utils import to_jsonable

from .exceptions import (
    AuthenticationError,
    ContextGraphConnectionError,
    NotFoundError,
    PermissionDeniedError,
    ServerError,
    ValidationError,
)


class Transport(Protocol):
    def register_agent(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def update_agent_defaults(self, payload: dict[str, Any]) -> dict[str, Any]: ...
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


@dataclass(slots=True)
class LocalTransport:
    service: ContextGraphService

    def register_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.register_agent(**payload))

    def update_agent_defaults(self, payload: dict[str, Any]) -> dict[str, Any]:
        local_payload = dict(payload)
        local_payload["requester_agent_id"] = local_payload["agent_id"]
        return to_jsonable(self.service.update_agent_defaults(**local_payload))

    def store(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.store_memory(**payload))

    def store_async(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.enqueue_memory_store(**payload))

    def update_memory_access(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.update_memory_access(**payload))

    def recall(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return to_jsonable(self.service.recall(**payload))

    def relate(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return to_jsonable(self.service.relate(**payload))

    def watch(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.watch(**payload))

    def list_watches(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return to_jsonable(self.service.list_standing_queries(**payload))

    def deactivate_watch(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.deactivate_watch(**payload))

    def job_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.get_job(**payload))

    def list_jobs(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return to_jsonable(self.service.list_jobs(**payload))

    def list_claims(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return to_jsonable(self.service.list_claims(**payload))

    def notifications(self, agent_id: str) -> list[dict[str, Any]]:
        return to_jsonable(self.service.get_notifications(agent_id=agent_id))

    def review_claim(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.review_claim(**payload))

    def review_queue(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return to_jsonable(self.service.list_review_queue(**payload))

    def operator_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.operator_snapshot(**payload))

    def expire_claims(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.enqueue_claim_expiry_sweep(**payload))


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


class ContextGraph:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    @classmethod
    def local(cls, service: ContextGraphService | None = None) -> ContextGraph:
        return cls(LocalTransport(service or ContextGraphService()))

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

    def store(
        self,
        agent_id: str,
        content: str,
        visibility: str | None = None,
        license: str = "internal",
        metadata: dict[str, str] | None = None,
        access_list: list[str] | None = None,
        price: float | None = None,
    ) -> dict[str, Any]:
        return self.transport.store(
            {
                "agent_id": agent_id,
                "content": content,
                "visibility": visibility,
                "license": license,
                "metadata": metadata or {},
                "access_list": access_list,
                "price": price,
            }
        )

    def store_async(
        self,
        agent_id: str,
        content: str,
        visibility: str | None = None,
        license: str = "internal",
        metadata: dict[str, str] | None = None,
        access_list: list[str] | None = None,
        price: float | None = None,
    ) -> dict[str, Any]:
        return self.transport.store_async(
            {
                "agent_id": agent_id,
                "content": content,
                "visibility": visibility,
                "license": license,
                "metadata": metadata or {},
                "access_list": access_list,
                "price": price,
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
