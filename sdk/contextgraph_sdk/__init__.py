from __future__ import annotations

from typing import TYPE_CHECKING

from .client import ContextGraph, HttpTransport
from .exceptions import (
    AuthenticationError,
    ContextGraphAPIError,
    ContextGraphConnectionError,
    ContextGraphSDKError,
    ContextGraphTransportError,
    MemoryDirectoryError,
    NotFoundError,
    PermissionDeniedError,
    ServerError,
    ValidationError,
)
from .policies import (
    MemoryContext,
    MemoryPolicyDecision,
    MemoryStoreOutcome,
    SharedMemoryDecision,
    SharedMemoryQueryContext,
    SharedMemoryRecallOutcome,
    SubscriptionContext,
    SubscriptionPlan,
)

if TYPE_CHECKING:
    from ._local import LocalTransport as LocalTransport
    from .policies import (
        MemoryPolicyHelper as MemoryPolicyHelper,
    )
    from .policies import (
        SharedMemoryHelper as SharedMemoryHelper,
    )
    from .policies import (
        SubscriptionPolicyManager as SubscriptionPolicyManager,
    )


def __getattr__(name: str) -> object:
    if name == "LocalTransport":
        from ._local import LocalTransport

        return LocalTransport
    if name in {"MemoryPolicyHelper", "SharedMemoryHelper", "SubscriptionPolicyManager"}:
        from . import policies

        return getattr(policies, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AuthenticationError",
    "ContextGraph",
    "ContextGraphAPIError",
    "ContextGraphConnectionError",
    "ContextGraphSDKError",
    "ContextGraphTransportError",
    "HttpTransport",
    "LocalTransport",
    "MemoryDirectoryError",
    "MemoryContext",
    "MemoryPolicyDecision",
    "MemoryPolicyHelper",
    "MemoryStoreOutcome",
    "NotFoundError",
    "PermissionDeniedError",
    "ServerError",
    "SharedMemoryDecision",
    "SharedMemoryHelper",
    "SharedMemoryQueryContext",
    "SharedMemoryRecallOutcome",
    "SubscriptionContext",
    "SubscriptionPlan",
    "SubscriptionPolicyManager",
    "ValidationError",
]
