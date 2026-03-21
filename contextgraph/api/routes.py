from __future__ import annotations

from typing import Any

from ..service import ContextGraphService
from ..utils import to_jsonable
from ._compat import Depends, Header
from .dependencies import build_authenticated_agent_dependency, require_same_agent
from .schemas import (
    AgentActivityResponse,
    AgentDefaultsUpdateRequest,
    AgentProfileResponse,
    AgentProfileUpdateRequest,
    AgentRegistrationRequest,
    AgentRegistrationResponse,
    AgentResponse,
    AgentSuspendRequest,
    AuditEntryResponse,
    BackgroundJobResponse,
    ClaimResponse,
    ClaimUpdateRequest,
    DiscoverAgentsResponse,
    FeedItemResponse,
    FollowRequest,
    MemoryAccessUpdateRequest,
    MemoryCurationUpdateRequest,
    MemoryResponse,
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
    SubscriptionResponse,
    TrustScoreResponse,
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
                default_visibility=payload.default_visibility.value if payload.default_visibility else None,
                default_access_list=payload.default_access_list,
                default_price=payload.default_price,
            )
        )

    @app.patch("/v1/agents/{agent_id}/defaults", response_model=AgentResponse)
    def update_agent_defaults(
        agent_id: str,
        payload: AgentDefaultsUpdateRequest,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        require_same_agent(
            authenticated,
            agent_id,
            "Agents may only update their own default memory policy.",
        )
        return to_jsonable(
            graph.update_agent_defaults(
                requester_agent_id=authenticated.agent_id,
                agent_id=agent_id,
                default_visibility=payload.default_visibility.value if payload.default_visibility else None,
                default_access_list=payload.default_access_list,
                default_price=payload.default_price,
            )
        )

    @app.get("/v1/agents", response_model=list[AgentResponse])
    def list_agents(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.list_agents(requester_agent_id=authenticated.agent_id))

    @app.get("/v1/agents/discover", response_model=DiscoverAgentsResponse)
    def discover_agents(
        q: str = "",
        status: str | None = None,
        min_reputation: float = 0.0,
        org_id: str | None = None,
        visibility: str | None = None,
        sort_by: str = "reputation",
        limit: int = 20,
        offset: int = 0,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        return to_jsonable(
            graph.discover_agents(
                requester_agent_id=authenticated.agent_id,
                q=q,
                status=status,
                min_reputation=min_reputation,
                org_id=org_id,
                visibility=visibility,
                sort_by=sort_by,
                limit=limit,
                offset=offset,
            )
        )

    @app.get("/v1/agents/{agent_id}", response_model=AgentProfileResponse)
    def get_agent_profile(agent_id: str, authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.get_agent_profile(requester_agent_id=authenticated.agent_id, agent_id=agent_id))

    @app.patch("/v1/agents/{agent_id}/profile", response_model=AgentProfileResponse)
    def update_agent_profile(
        agent_id: str,
        payload: AgentProfileUpdateRequest,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        require_same_agent(
            authenticated,
            agent_id,
            "Agents may only update their own discovery profile.",
        )
        return to_jsonable(
            graph.update_agent_profile(
                requester_agent_id=authenticated.agent_id,
                agent_id=agent_id,
                profile_visibility=payload.profile_visibility.value if payload.profile_visibility else None,
                profile_access_list=payload.profile_access_list,
                profile_summary=payload.profile_summary,
                profile_links=payload.profile_links,
            )
        )

    @app.get("/v1/agents/{agent_id}/activity", response_model=AgentActivityResponse)
    def agent_activity(
        agent_id: str,
        limit: int = 20,
        offset: int = 0,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        return to_jsonable(
            graph.get_agent_activity(
                requester_agent_id=authenticated.agent_id,
                agent_id=agent_id,
                limit=limit,
                offset=offset,
            )
        )

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
                visibility=payload.visibility.value if payload.visibility else None,
                license=payload.license,
                metadata=payload.metadata,
                evidence=payload.evidence,
                citations=payload.citations,
                access_list=payload.access_list,
                price=payload.price,
                expires_in_days=payload.expires_in_days,
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
                visibility=payload.visibility.value if payload.visibility else None,
                license=payload.license,
                metadata=payload.metadata,
                evidence=payload.evidence,
                citations=payload.citations,
                access_list=payload.access_list,
                price=payload.price,
                expires_in_days=payload.expires_in_days,
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
        include_inactive: bool = False,
        only_needing_review: bool = False,
        limit: int = 100,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        return to_jsonable(
            graph.list_claims(
                requester_agent_id=authenticated.agent_id,
                validation_status=validation_status,
                include_inactive=include_inactive,
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

    @app.get("/v1/feed", response_model=list[FeedItemResponse])
    def feed(
        limit: int = 20,
        offset: int = 0,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        return to_jsonable(
            graph.get_feed(
                agent_id=authenticated.agent_id,
                limit=min(limit, 100),
                offset=max(offset, 0),
            )
        )

    @app.post("/v1/follow", response_model=SubscriptionResponse, status_code=201)
    def follow(payload: FollowRequest, authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(
            graph.follow(
                agent_id=authenticated.agent_id,
                target_type=payload.target_type.value,
                target_id=payload.target_id,
            )
        )

    @app.delete("/v1/follow/{subscription_id}", status_code=204, response_model=None)
    def unfollow(subscription_id: str, authenticated: Any = Depends(authenticated_agent)) -> None:
        graph.unfollow(agent_id=authenticated.agent_id, subscription_id=subscription_id)

    @app.get("/v1/following", response_model=list[SubscriptionResponse])
    def following(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.list_following(agent_id=authenticated.agent_id))

    @app.get("/v1/followers", response_model=list[SubscriptionResponse])
    def followers(authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.list_followers(agent_id=authenticated.agent_id))

    @app.get("/v1/agents/{agent_id}/trust", response_model=TrustScoreResponse)
    def trust_score(agent_id: str, authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(graph.get_agent_trust_summary(authenticated.agent_id, agent_id))

    @app.patch("/v1/claims/{claim_id}", response_model=ClaimResponse)
    def update_claim(
        claim_id: str, payload: ClaimUpdateRequest, authenticated: Any = Depends(authenticated_agent)
    ) -> Any:
        return to_jsonable(
            graph.update_claim(
                requester_agent_id=authenticated.agent_id,
                claim_id=claim_id,
                visibility=payload.visibility.value if payload.visibility else None,
                price=payload.price,
                access_list=payload.access_list,
            )
        )

    @app.patch("/v1/memories/{memory_id}/access", response_model=MemoryResponse)
    def update_memory_access(
        memory_id: str, payload: MemoryAccessUpdateRequest, authenticated: Any = Depends(authenticated_agent)
    ) -> Any:
        return to_jsonable(
            graph.update_memory_access(
                requester_agent_id=authenticated.agent_id,
                memory_id=memory_id,
                visibility=payload.visibility.value if payload.visibility else None,
                price=payload.price,
                access_list=payload.access_list,
            )
        )

    @app.get("/v1/memories", response_model=list[MemoryResponse])
    def list_memories(
        include_inactive: bool = False,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        return to_jsonable(
            graph.list_memories(
                requester_agent_id=authenticated.agent_id,
                include_private_same_org=True,
                include_inactive=include_inactive,
            )
        )

    @app.get("/v1/memories/{memory_id}", response_model=MemoryResponse)
    def get_memory(memory_id: str, authenticated: Any = Depends(authenticated_agent)) -> Any:
        return to_jsonable(
            graph.get_memory_for_agent(
                requester_agent_id=authenticated.agent_id,
                memory_id=memory_id,
                include_private_same_org=True,
                include_inactive=True,
            )
        )

    @app.patch("/v1/memories/{memory_id}/curation", response_model=MemoryResponse)
    def update_memory_curation(
        memory_id: str, payload: MemoryCurationUpdateRequest, authenticated: Any = Depends(authenticated_agent)
    ) -> Any:
        return to_jsonable(
            graph.update_memory_curation(
                requester_agent_id=authenticated.agent_id,
                memory_id=memory_id,
                curation_status=payload.curation_status.value,
                reason=payload.reason,
            )
        )

    # --- Agent Lifecycle ---

    @app.post("/v1/agents/{agent_id}/suspend")
    def suspend_agent(
        agent_id: str,
        payload: AgentSuspendRequest,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        target = graph.get_agent(agent_id)
        if authenticated.org_id != target.org_id:
            from ._compat import HTTPException

            raise HTTPException(status_code=403, detail="Can only suspend agents in your org.")
        return to_jsonable(graph.suspend_agent(authenticated.agent_id, agent_id, reason=payload.reason))

    @app.post("/v1/agents/{agent_id}/reactivate")
    def reactivate_agent(
        agent_id: str,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        target = graph.get_agent(agent_id)
        if authenticated.org_id != target.org_id:
            from ._compat import HTTPException

            raise HTTPException(status_code=403, detail="Can only reactivate agents in your org.")
        return to_jsonable(graph.reactivate_agent(authenticated.agent_id, agent_id))

    @app.delete("/v1/agents/{agent_id}")
    def delete_agent(
        agent_id: str,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        target = graph.get_agent(agent_id)
        if authenticated.org_id != target.org_id:
            from ._compat import HTTPException

            raise HTTPException(status_code=403, detail="Can only delete agents in your org.")
        return to_jsonable(graph.delete_agent(authenticated.agent_id, agent_id))

    # --- Sentinel Audit ---

    @app.get("/v1/audit/verdicts")
    def list_verdicts(
        claim_id: str | None = None,
        decision: str | None = None,
        limit: int = 100,
        authenticated: Any = Depends(authenticated_agent),
    ) -> Any:
        if claim_id:
            results = graph.list_verdicts_for_claim(claim_id)
        else:
            results = graph.list_verdicts(limit=limit, decision=decision)
        return to_jsonable(results)

    @app.get("/v1/sentinel/health")
    def sentinel_health(authenticated: Any = Depends(authenticated_agent)) -> Any:
        sentinels = [a for a in graph.repository.list_agents() if a.role == "sentinel"]
        return {
            "sentinels_active": len([s for s in sentinels if s.status == "active"]),
            "total_verdicts": len(graph.repository.list_verdicts()),
            "last_canary_passed": None,
        }
