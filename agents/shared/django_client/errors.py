"""Exceptions raised by the shared Django HTTP client."""


class DjangoClientError(Exception):
    """Base exception for Django HTTP client failures."""


class DjangoConnectionError(DjangoClientError):
    """Raised when the client cannot reach the Django API."""


class DjangoTimeoutError(DjangoClientError):
    """Raised when a Django API request exceeds the configured timeout."""


class DjangoHTTPError(DjangoClientError):
    """Raised when Django returns a non-2xx HTTP status."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


class DjangoJSONError(DjangoClientError):
    """Raised when a JSON response was expected but could not be parsed."""
