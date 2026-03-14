from __future__ import annotations


class ContextGraphSDKError(Exception):
    """Base SDK error."""


class ContextGraphTransportError(ContextGraphSDKError):
    """Transport-level failure."""


class ContextGraphConnectionError(ContextGraphTransportError):
    """Could not reach the ContextGraph service."""


class ContextGraphAPIError(ContextGraphSDKError):
    """Structured API error returned by the server."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(ContextGraphAPIError):
    """Authentication failed."""


class PermissionDeniedError(ContextGraphAPIError):
    """Requester is not allowed to perform the action."""


class NotFoundError(ContextGraphAPIError):
    """Requested resource does not exist."""


class ValidationError(ContextGraphAPIError):
    """Request payload or operation parameters were invalid."""


class ServerError(ContextGraphAPIError):
    """The server failed while processing the request."""
