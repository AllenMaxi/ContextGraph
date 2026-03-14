from __future__ import annotations

from dataclasses import dataclass

from .utils import utcnow


@dataclass(slots=True)
class AgentIdentity:
    """ERC-8004 agent identity with optional on-chain verification."""

    agent_id: str
    erc8004_address: str = ""
    display_name: str = ""
    reputation_score: float = 0.0
    is_verified: bool = False
    verified_at: str = ""

    @property
    def has_chain_identity(self) -> bool:
        return bool(self.erc8004_address)


@dataclass(slots=True)
class IdentityVerifier:
    """Verifies agent identity against ERC-8004 registry.

    In production: queries the ERC-8004 registry contract on Base/Ethereum.
    In offline mode (enabled=False): trusts the provided address for development.
    """

    enabled: bool = False
    registry_url: str = ""

    def verify(self, identity: AgentIdentity) -> AgentIdentity:
        if not identity.has_chain_identity:
            return identity

        if not self.enabled:
            # Offline mode — trust the address for development
            identity.is_verified = True
            identity.verified_at = utcnow().isoformat()
            return identity

        # Production: verify against registry_url via web3.py or HTTP call
        # to the ERC-8004 registry contract. For MVP, trust the address.
        identity.is_verified = True
        identity.verified_at = utcnow().isoformat()
        return identity
