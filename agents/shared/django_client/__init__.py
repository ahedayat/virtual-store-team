"""Shared Django internal API HTTP client for AI agent services."""

from agents.shared.django_client.client import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    DjangoClient,
    join_url,
    normalize_base_url,
)
from agents.shared.django_client.errors import (
    DjangoClientError,
    DjangoConnectionError,
    DjangoHTTPError,
    DjangoJSONError,
    DjangoTimeoutError,
)

__all__ = [
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_BACKOFF_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "DjangoClient",
    "DjangoClientError",
    "DjangoConnectionError",
    "DjangoHTTPError",
    "DjangoJSONError",
    "DjangoTimeoutError",
    "join_url",
    "normalize_base_url",
]
