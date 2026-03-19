"""UCP (Universal Commerce Protocol) endpoints for knowledge marketplace.

Exposes ContextGraph's published, priced claims through a standard commerce
interface so any UCP-compatible agent can discover and purchase knowledge.
"""

from __future__ import annotations

from typing import Any

from ..errors import NotFoundError, PaymentRequiredError
from ..models import Visibility
from ..service import ContextGraphService
from ..utils import to_jsonable
from ._compat import Depends, Header


def register_ucp_routes(app: Any, graph: ContextGraphService) -> None:
    """Register UCP commerce endpoints."""

    from .dependencies import build_authenticated_agent_dependency

    authenticated_agent = build_authenticated_agent_dependency(graph)

    # ------------------------------------------------------------------
    # Discovery: /.well-known/ucp
    # ------------------------------------------------------------------

    @app.get("/.well-known/ucp")
    def ucp_discovery() -> dict[str, Any]:
        return {
            "name": "ContextGraph Knowledge Marketplace",
            "version": "1.0",
            "protocol": "ucp",
            "capabilities": ["catalog", "checkout", "fulfillment"],
            "endpoints": {
                "catalog": "/v1/ucp/catalog",
                "checkout": "/v1/ucp/checkout",
                "fulfillment": "/v1/ucp/fulfillment/{order_id}",
            },
            "supported_currencies": [graph.settings.payment_currency],
            "payment_protocols": ["x402"],
        }

    # ------------------------------------------------------------------
    # Catalog: list purchasable knowledge
    # ------------------------------------------------------------------

    @app.get("/v1/ucp/catalog")
    def ucp_catalog(
        page: int = 1,
        per_page: int = 20,
        entity: str | None = None,
        min_confidence: float = 0.0,
    ) -> dict[str, Any]:
        all_claims = graph.repository.list_claims()
        # Only published claims with a price
        priced = [c for c in all_claims if c.visibility == Visibility.PUBLISHED and c.price > 0]

        # Optional entity filter
        if entity:
            from ..utils import normalize_alias

            alias = normalize_alias(entity)
            filtered = []
            for claim in priced:
                for eid in claim.entity_ids:
                    e = graph.repository.get_entity(eid)
                    if e and e.alias_key == alias:
                        filtered.append(claim)
                        break
            priced = filtered

        # Confidence filter
        if min_confidence > 0:
            priced = [c for c in priced if c.confidence >= min_confidence]

        # Sort by freshness
        priced.sort(key=lambda c: c.created_at, reverse=True)
        total = len(priced)

        # Paginate
        start = (page - 1) * per_page
        page_items = priced[start : start + per_page]

        items = []
        for claim in page_items:
            source = graph.repository.get_agent(claim.source_agent_id)
            entities = []
            for eid in claim.entity_ids:
                e = graph.repository.get_entity(eid)
                if e:
                    entities.append(e.name)
            items.append(
                {
                    "item_id": claim.claim_id,
                    "name": claim.statement[:80],
                    "description": claim.statement,
                    "price": {
                        "amount": f"{claim.price:.6f}",
                        "currency": graph.settings.payment_currency,
                    },
                    "seller": {
                        "agent_id": claim.source_agent_id,
                        "org_id": claim.source_org_id,
                        "name": source.name if source else "",
                        "reputation": source.reputation_score if source else 0.0,
                    },
                    "metadata": {
                        "entity_count": len(claim.entity_ids),
                        "entities": entities,
                        "confidence": claim.confidence,
                        "impact": claim.impact.value,
                        "validation_status": claim.validation_status.value,
                        "quorum_met": claim.quorum_met,
                        "created_at": claim.created_at.isoformat(),
                    },
                }
            )

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    # ------------------------------------------------------------------
    # Checkout: purchase a claim
    # ------------------------------------------------------------------

    @app.post("/v1/ucp/checkout")
    def ucp_checkout(
        payload: dict[str, Any],
        authenticated: Any = Depends(authenticated_agent),
        x_payment_token: str | None = Header(default=None, alias="X-Payment-Token"),
    ) -> dict[str, Any]:
        claim_id = payload.get("item_id", "")
        if not claim_id:
            return {"error": "item_id is required", "status": "failed"}

        claim = graph.repository.get_claim(claim_id)
        if claim is None:
            raise NotFoundError(f"Claim '{claim_id}' not found.")

        if claim.visibility != Visibility.PUBLISHED or claim.price <= 0:
            return {"error": "Item is not available for purchase", "status": "failed"}

        # Try to recall with payment — this enforces x402
        try:
            graph.recall(
                agent_id=authenticated.agent_id,
                query=claim.statement,
                limit=1,
                payment_token=x_payment_token,
            )
        except PaymentRequiredError:
            return {
                "status": "payment_required",
                "price": {
                    "amount": f"{claim.price:.6f}",
                    "currency": graph.settings.payment_currency,
                },
                "payment_protocols": ["x402"],
                "message": "Payment required. Include X-Payment-Token header.",
            }

        # Find the matching hit
        memory = graph.repository.get_memory(claim.memory_id)
        return {
            "status": "completed",
            "order_id": f"ord-{claim.claim_id}",
            "item": {
                "claim_id": claim.claim_id,
                "statement": claim.statement,
                "memory_content": memory.content if memory else "",
                "confidence": claim.confidence,
                "entities": [
                    graph.repository.get_entity(eid).name
                    for eid in claim.entity_ids
                    if graph.repository.get_entity(eid)
                ],
                "provenance": to_jsonable(claim.provenance),
            },
        }

    # ------------------------------------------------------------------
    # Fulfillment: check order status
    # ------------------------------------------------------------------

    @app.get("/v1/ucp/fulfillment/{order_id}")
    def ucp_fulfillment(order_id: str) -> dict[str, Any]:
        # Order IDs are formatted as "ord-{claim_id}"
        if not order_id.startswith("ord-"):
            return {"error": "Invalid order ID format", "status": "not_found"}
        claim_id = order_id[4:]
        claim = graph.repository.get_claim(claim_id)
        if claim is None:
            return {"error": "Order not found", "status": "not_found"}
        return {
            "order_id": order_id,
            "status": "fulfilled",
            "item_id": claim.claim_id,
            "created_at": claim.created_at.isoformat(),
        }
