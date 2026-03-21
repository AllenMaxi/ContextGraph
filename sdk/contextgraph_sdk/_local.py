from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contextgraph.service import ContextGraphService
from contextgraph.utils import to_jsonable


@dataclass(slots=True)
class LocalTransport:
    service: ContextGraphService

    def register_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.register_agent(**payload))

    def update_agent_defaults(self, payload: dict[str, Any]) -> dict[str, Any]:
        local_payload = dict(payload)
        local_payload["requester_agent_id"] = local_payload["agent_id"]
        return to_jsonable(self.service.update_agent_defaults(**local_payload))

    def get_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(
            self.service.get_agent_profile(
                requester_agent_id=payload["requester_agent_id"],
                agent_id=payload["agent_id"],
            )
        )

    def agent_trust(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(
            self.service.get_agent_trust_summary(
                requester_agent_id=payload["requester_agent_id"],
                agent_id=payload["agent_id"],
            )
        )

    def update_agent_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        local_payload = dict(payload)
        return to_jsonable(self.service.update_agent_profile(**local_payload))

    def discover_agents(self, payload: dict[str, Any]) -> dict[str, Any]:
        local_payload = dict(payload)
        return to_jsonable(self.service.discover_agents(**local_payload))

    def agent_activity(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(
            self.service.get_agent_activity(
                requester_agent_id=payload["requester_agent_id"],
                agent_id=payload["agent_id"],
                limit=payload.get("limit", 20),
                offset=payload.get("offset", 0),
            )
        )

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

    def follow(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(
            self.service.follow(
                agent_id=payload["agent_id"],
                target_type=payload["target_type"],
                target_id=payload["target_id"],
            )
        )

    def unfollow(self, payload: dict[str, Any]) -> None:
        self.service.unfollow(
            agent_id=payload["agent_id"],
            subscription_id=payload["subscription_id"],
        )
        return None

    def list_following(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return to_jsonable(self.service.list_following(agent_id=payload["agent_id"]))

    def list_followers(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return to_jsonable(self.service.list_followers(agent_id=payload["agent_id"]))

    def feed(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return to_jsonable(
            self.service.get_feed(
                agent_id=payload["agent_id"],
                limit=payload.get("limit", 20),
                offset=payload.get("offset", 0),
            )
        )

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

    def suspend_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(
            self.service.suspend_agent(
                requester_agent_id=payload["agent_id"],
                agent_id=payload["agent_id"],
                reason=payload.get("reason", "manual"),
            )
        )

    def reactivate_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(
            self.service.reactivate_agent(
                requester_agent_id=payload["agent_id"],
                agent_id=payload["agent_id"],
            )
        )

    def delete_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(
            self.service.delete_agent(
                requester_agent_id=payload["agent_id"],
                agent_id=payload["agent_id"],
            )
        )

    def sentinel_verdicts(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        claim_id = payload.get("claim_id")
        if claim_id:
            return to_jsonable(self.service.list_verdicts_for_claim(claim_id))
        return to_jsonable(self.service.list_verdicts(decision=payload.get("decision")))

    def sentinel_health(self, payload: dict[str, Any]) -> dict[str, Any]:
        sentinels = [a for a in self.service.repository.list_agents() if a.role == "sentinel"]
        return {
            "sentinels_active": len([s for s in sentinels if s.status == "active"]),
            "total_verdicts": len(self.service.repository.list_verdicts()),
            "last_canary_passed": None,
        }
