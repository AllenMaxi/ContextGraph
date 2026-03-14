from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass
from typing import Protocol
from urllib import request
from urllib.parse import urlparse

from .models import Claim, Notification, StandingQuery
from .utils import to_jsonable

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
]


def validate_webhook_url(url: str) -> None:
    """Validate that a webhook URL doesn't target private/internal networks."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"webhook URL must use http or https, got {parsed.scheme}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("webhook URL must have a hostname")
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                raise ValueError(f"webhook URL must not target private network: {hostname}")
    except ValueError as exc:
        if "private network" in str(exc) or "must use" in str(exc) or "must have" in str(exc):
            raise
        # hostname is a domain name, not an IP — allow (DNS resolves at dispatch time)


@dataclass(slots=True)
class DeliveryRequest:
    notification: Notification
    query: StandingQuery
    claim: Claim
    webhook_url: str


class NotificationDispatcher(Protocol):
    def dispatch(self, delivery: DeliveryRequest) -> None: ...


@dataclass(slots=True)
class WebhookNotificationDispatcher:
    timeout_seconds: float = 5.0
    user_agent: str = "ContextGraph/0.1"

    def dispatch(self, delivery: DeliveryRequest) -> None:
        payload = to_jsonable(
            {
                "event_type": delivery.notification.event_type,
                "notification": delivery.notification,
                "query": delivery.query,
                "claim": delivery.claim,
            }
        )
        req = request.Request(
            delivery.webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            },
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_seconds):  # noqa: S310 - operator configures endpoint
            return None
