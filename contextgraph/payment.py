from __future__ import annotations

from dataclasses import dataclass

from .errors import PaymentRequiredError


@dataclass(slots=True)
class PaymentReceipt:
    """Proof of payment for a knowledge access."""
    token: str
    amount: float
    currency: str
    payer_agent_id: str
    status: str  # "verified" or "pending"


@dataclass(slots=True)
class PaymentPolicy:
    """Pricing policy for an agent's knowledge."""
    default_price: float = 0.0
    currency: str = "USDC"

    def price_for_claim(self, claim_id: str) -> float:
        return self.default_price


@dataclass(slots=True)
class PaymentGate:
    """Gate that checks x402 payment before granting access to priced knowledge.

    When enabled, cross-org access to priced claims requires an x402 payment
    token in the X-Payment-Token header. Same-org agents never pay each other.
    """
    enabled: bool = False

    def check_access(
        self,
        agent_id: str,
        claim_price: float,
        payment_token: str | None,
        requester_org: str = "",
        claim_org: str = "",
    ) -> PaymentReceipt | None:
        """Check if payment is satisfied. Raises PaymentRequiredError if not."""
        if not self.enabled:
            return None

        # Same-org agents don't pay each other
        if requester_org and claim_org and requester_org == claim_org:
            return None

        # Free claims need no payment
        if claim_price <= 0:
            return None

        # Priced claim requires token
        if not payment_token:
            raise PaymentRequiredError(
                f"Payment required: {claim_price} USDC. "
                f"Send x402 payment token in X-Payment-Token header."
            )

        # In production, verify token against x402 settlement network.
        # For MVP, accept any non-empty token as valid.
        return PaymentReceipt(
            token=payment_token,
            amount=claim_price,
            currency="USDC",
            payer_agent_id=agent_id,
            status="verified",
        )
