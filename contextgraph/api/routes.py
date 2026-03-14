from __future__ import annotations

from typing import Any

from ..service import ContextGraphService
from ..utils import to_jsonable
from ._compat import Depends, Header
from .dependencies import build_authenticated_agent_dependency, require_same_agent
from .schemas import (
    AgentRegistrationRequest,
    AgentRegistrationResponse,
    AgentResponse,
    AuditEntryResponse,
    BackgroundJobResponse,
    ClaimResponse,
    MemoryStoreRequest,
    NotificationResponse,
    OperatorSummaryResponse,
    RecallHitResponse,
    RecallRequest,
    RelateRequest,
    RelationPathResponse,
    ReviewClaimRequest,
    ReviewQueueItemResponse,
    ReviewTaskResponse,
    StandingQueryResponse,
    StoreResultResponse,
    WatchRequest,
)


def register_routes(app: Any, graph: ContextGraphService) -> None:
    authenticated_agent = build_authenticated_agent_dependency(graph)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return graph.health()

    @app.post("/v1/agents/register", response_model=AgentRegistrationResponse, status_code=201)
    def register_agent(
        payload: AgentRegistrationRequest,
        x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    ) -> Any:
        return to_jsonable(
            graph.register_agent(
                name=payload.name,
                org_id=payload.org_id,
                capabilities=payload.capabilities,
                admin_key=x_admin_key,
                erc8004_address=payload.erc8004_address,
            )
        )

    @app.get("/v1/agents", response_model=list[AgentResponse])
    def list_agents(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.list_agents(requester_agent_id=authenticated.agent_id))

    @app.post("/v1/memory/store", response_model=StoreResultResponse)
    def store_memory(payload: MemoryStoreRequest, authenticated: Any = Depends(authenticated_agent)) -> Any:
        require_same_agent(
            authenticated,
            payload.agent_id,
            "Authenticated agent does not match the requested agent_id.",
        )
        return to_jsonable(
            graph.store_memory(
                agent_id=authenticated.agent_id,
                content=payload.content,
                visibility=payload.visibility.value,
                license=payload.license,
                metadata=payload.metadata,
                access_list=payload.access_list,
                price=payload.price,
            )
        )

    @app.post("/v1/memory/store-async", response_model=BackgroundJobResponse)
    def store_memory_async(payload: MemoryStoreRequest, authenticated: Any = Depends(authenticated_agent)) -> Any:
        require_same_agent(
            authenticated,
            payload.agent_id,
            "Authenticated agent does not match the requested agent_id.",
        )
        return to_jsonable(
            graph.enqueue_memory_store(
                agent_id=authenticated.agent_id,
                content=payload.content,
                visibility=payload.visibility.value,
                license=payload.license,
                metadata=payload.metadata,
            )
        )

    @app.post("/v1/memory/recall", response_model=list[RecallHitResponse])
    def recall(
        payload: RecallRequest,
        authenticated: Any = Depends(authenticated_agent),
        x_payment_token: str | None = Header(default=None, alias="X-Payment-Token"),
    ) -> Any:
        require_same_agent(
            authenticated,
            payload.agent_id,
            "Authenticated agent does not match the requested agent_id.",
        )
        return to_jsonable(
            graph.recall(
                agent_id=authenticated.agent_id,
                query=payload.query,
                limit=payload.limit,
                payment_token=x_payment_token,
            )
        )

    @app.post("/v1/memory/relate", response_model=list[RelationPathResponse])
    def relate(payload: RelateRequest, authenticated: Any = Depends(authenticated_agent)) -> Any:
        require_same_agent(
            authenticated,
            payload.agent_id,
            "Authenticated agent does not match the requested agent_id.",
        )
        return to_jsonable(
            graph.relate(
                agent_id=authenticated.agent_id,
                entity_a=payload.entity_a,
                entity_b=payload.entity_b,
                max_depth=payload.max_depth,
            )
        )

    @app.post("/v1/watch", response_model=StandingQueryResponse)
    def watch(payload: WatchRequest, authenticated: Any = Depends(authenticated_agent)) -> Any:
        require_same_agent(
            authenticated,
            payload.agent_id,
            "Authenticated agent does not match the requested agent_id.",
        )
        return to_jsonable(
            graph.watch(
                agent_id=authenticated.agent_id,
                query=payload.query,
                name=payload.name,
                delivery_mode=payload.delivery_mode.value,
                filters=payload.filters,
            )
        )

    @app.get("/v1/watch", response_model=list[StandingQueryResponse])
    def list_watches(
        include_inactive: bool = False,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        return to_jsonable(
            graph.list_standing_queries(
                requester_agent_id=authenticated.agent_id,
                include_inactive=include_inactive,
            )
        )

    @app.post("/v1/watch/{query_id}/deactivate", response_model=StandingQueryResponse)
    def deactivate_watch(query_id: str, authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(
            graph.deactivate_watch(
                requester_agent_id=authenticated.agent_id,
                query_id=query_id,
            )
        )

    @app.get("/v1/notifications/{agent_id}", response_model=list[NotificationResponse])
    def notifications(
        agent_id: str,
        mark_delivered: bool = False,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        require_same_agent(
            authenticated,
            agent_id,
            "Agents may only access their own notifications.",
        )
        return to_jsonable(graph.get_notifications(agent_id=authenticated.agent_id, mark_delivered=mark_delivered))

    @app.get("/v1/jobs/{job_id}", response_model=BackgroundJobResponse)
    def job_status(job_id: str, authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.get_job(job_id=job_id, requester_agent_id=authenticated.agent_id))

    @app.get("/v1/jobs", response_model=list[BackgroundJobResponse])
    def list_jobs(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.list_jobs(requester_agent_id=authenticated.agent_id))

    @app.get("/v1/claims", response_model=list[ClaimResponse])
    def list_claims(
        validation_status: str | None = None,
        only_needing_review: bool = False,
        limit: int = 100,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        return to_jsonable(
            graph.list_claims(
                requester_agent_id=authenticated.agent_id,
                validation_status=validation_status,
                only_needing_review=only_needing_review,
                limit=limit,
            )
        )

    @app.get("/v1/claims/{claim_id}", response_model=ClaimResponse)
    def get_claim(claim_id: str, authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.get_claim_for_agent(requester_agent_id=authenticated.agent_id, claim_id=claim_id))

    @app.post("/v1/claims/review", response_model=ClaimResponse)
    def review_claim(payload: ReviewClaimRequest, authenticated: Any = Depends(authenticated_agent)) -> Any:
        require_same_agent(
            authenticated,
            payload.reviewer_agent_id,
            "Authenticated agent does not match the requested reviewer_agent_id.",
        )
        return to_jsonable(
            graph.review_claim(
                reviewer_agent_id=authenticated.agent_id,
                claim_id=payload.claim_id,
                decision=payload.decision.value,
                reason=payload.reason,
            )
        )

    @app.get("/v1/reviews", response_model=list[ReviewTaskResponse])
    def review_tasks(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.list_review_tasks(requester_agent_id=authenticated.agent_id))

    @app.get("/v1/review-queue", response_model=list[ReviewQueueItemResponse])
    def review_queue(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.list_review_queue(requester_agent_id=authenticated.agent_id))

    @app.get("/v1/operator/summary", response_model=OperatorSummaryResponse)
    def operator_summary(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.operator_snapshot(requester_agent_id=authenticated.agent_id))

    @app.post("/v1/maintenance/claims/expire", response_model=BackgroundJobResponse)
    def expire_claims(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.enqueue_claim_expiry_sweep(requester_agent_id=authenticated.agent_id))

    @app.get("/v1/audit", response_model=list[AuditEntryResponse])
    def audit_entries(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.list_audit_entries(requester_agent_id=authenticated.agent_id))
