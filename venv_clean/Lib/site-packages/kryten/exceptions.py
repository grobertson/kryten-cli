"""Exception hierarchy for kryten-py library."""


class KrytenError(Exception):
    """Base exception for all Kryten library errors."""


class KrytenConnectionError(KrytenError):
    """NATS connection failed or lost."""


class KrytenValidationError(KrytenError):
    """Invalid configuration or data."""


class KrytenTimeoutError(KrytenError):
    """Operation timed out."""


class PublishError(KrytenError):
    """Failed to publish command to NATS."""


class HandlerError(KrytenError):
    """Event handler raised unhandled exception."""


__all__ = [
    "KrytenError",
    "KrytenConnectionError",
    "KrytenValidationError",
    "KrytenTimeoutError",
    "PublishError",
    "HandlerError",
]
