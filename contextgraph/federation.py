"""Federation layer for cross-node claim sharing between ContextGraph instances."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib import request
from urllib.error import HTTPError, URLError

from .delivery import validate_webhook_url
from .models import Claim, Visibility
from .utils import to_jsonable, utcnow

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FederationPeer:
    """A remote ContextGraph node that participates in federation."""

    node_id: str
    base_url: str
    api_key: str
    name: str = ""
    enabled: bool = True
    last_sync_at: str | None = None


@dataclass(slots=True)
class FederationEvent:
    """An event sent between federated nodes."""

    event_type: str  # claim.published, claim.updated, claim.expired
    source_node_id: str
    claim: dict[str, Any]
    timestamp: str


@dataclass(slots=True)
class FederationResult:
    """Result of a federation sync operation."""

    peer_node_id: str
    claims_sent: int = 0
    claims_received: int = 0
    errors: list[str] = field(default_factory=list)
    success: bool = True


class FederationTransport(Protocol):
    """Protocol for sending claims to peer nodes."""

    def send_claims(self, peer: FederationPeer, claims: list[dict[str, Any]]) -> FederationResult: ...
    def fetch_claims(self, peer: FederationPeer, since: str | None = None) -> list[dict[str, Any]]: ...


@dataclass(slots=True)
class HttpFederationTransport:
    """HTTP-based federation transport using ContextGraph REST API."""

    timeout_seconds: float = 10.0
    user_agent: str = "ContextGraph-Federation/0.1"

    def send_claims(self, peer: FederationPeer, claims: list[dict[str, Any]]) -> FederationResult:
        result = FederationResult(peer_node_id=peer.node_id)
        if not claims:
            return result

        url = f"{peer.base_url.rstrip('/')}/v1/federation/ingest"
        payload = json.dumps({"claims": claims, "source_node_id": peer.node_id}).encode("utf-8")

        req = request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
                "X-Federation-Key": peer.api_key,
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                result.claims_sent = len(claims)
                result.claims_received = body.get("ingested", 0)
        except (HTTPError, URLError, OSError) as exc:
            result.success = False
            result.errors.append(str(exc))
            logger.warning("Federation send to %s failed: %s", peer.node_id, exc)

        return result

    def fetch_claims(self, peer: FederationPeer, since: str | None = None) -> list[dict[str, Any]]:
        url = f"{peer.base_url.rstrip('/')}/v1/federation/claims"
        if since:
            url += f"?since={since}"

        req = request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "X-Federation-Key": peer.api_key,
            },
            method="GET",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("claims", [])
        except (HTTPError, URLError, OSError) as exc:
            logger.warning("Federation fetch from %s failed: %s", peer.node_id, exc)
            return []


class FederationManager:
    """Manages federation of claims between ContextGraph nodes.

    Only PUBLISHED claims are federated by default. The manager filters
    claims by visibility before sending to peers.
    """

    def __init__(
        self,
        node_id: str,
        peers: list[FederationPeer] | None = None,
        transport: FederationTransport | None = None,
        enabled: bool = False,
    ) -> None:
        self.node_id = node_id
        self.peers: list[FederationPeer] = peers or []
        self.transport: FederationTransport = transport or HttpFederationTransport()
        self.enabled = enabled
        self._federated_claim_ids: set[str] = set()
        self._sync_count = 0

    def add_peer(self, peer: FederationPeer) -> None:
        if any(p.node_id == peer.node_id for p in self.peers):
            return
        validate_webhook_url(peer.base_url)
        self.peers.append(peer)

    def remove_peer(self, node_id: str) -> None:
        self.peers = [p for p in self.peers if p.node_id != node_id]

    def should_federate(self, claim: Claim) -> bool:
        """Only federate PUBLISHED claims that haven't been sent yet."""
        if not self.enabled:
            return False
        if claim.visibility != Visibility.PUBLISHED:
            return False
        if claim.claim_id in self._federated_claim_ids:
            return False
        return True

    def federate_claims(self, claims: list[Claim]) -> list[FederationResult]:
        """Send eligible claims to all active peers."""
        if not self.enabled:
            return []

        eligible = [c for c in claims if self.should_federate(c)]
        if not eligible:
            return []

        claim_dicts = [to_jsonable(c) for c in eligible]
        results: list[FederationResult] = []

        for peer in self.peers:
            if not peer.enabled:
                continue
            result = self.transport.send_claims(peer, claim_dicts)
            if result.success:
                for c in eligible:
                    self._federated_claim_ids.add(c.claim_id)
                peer.last_sync_at = utcnow().isoformat()
            results.append(result)
            self._sync_count += 1

        return results

    def fetch_from_peers(self) -> list[dict[str, Any]]:
        """Pull published claims from all active peers."""
        if not self.enabled:
            return []

        all_claims: list[dict[str, Any]] = []
        for peer in self.peers:
            if not peer.enabled:
                continue
            claims = self.transport.fetch_claims(peer, since=peer.last_sync_at)
            all_claims.extend(claims)
            if claims:
                peer.last_sync_at = utcnow().isoformat()
            self._sync_count += 1

        return all_claims

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "node_id": self.node_id,
            "peer_count": len(self.peers),
            "peers": [
                {
                    "node_id": p.node_id,
                    "name": p.name,
                    "enabled": p.enabled,
                    "last_sync_at": p.last_sync_at,
                }
                for p in self.peers
            ],
            "federated_claims": len(self._federated_claim_ids),
            "sync_operations": self._sync_count,
        }
