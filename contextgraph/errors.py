class ContextGraphError(Exception):
    """Base error for ContextGraph."""


class NotFoundError(ContextGraphError):
    """Requested resource does not exist."""


class PermissionDeniedError(ContextGraphError):
    """Requester is not allowed to access the resource."""


class ConflictError(ContextGraphError):
    """Operation cannot be completed because of current state."""


class AuthenticationError(ContextGraphError):
    """Requester could not be authenticated."""


class PaymentRequiredError(ContextGraphError):
    """Raised when payment is required to access a resource."""
