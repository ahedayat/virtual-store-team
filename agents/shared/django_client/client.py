"""HTTP client for AI services calling Django internal APIs."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from agents.shared.django_client.errors import (
    DjangoConnectionError,
    DjangoHTTPError,
    DjangoJSONError,
    DjangoTimeoutError,
)

_ENV_BASE_URL = "DJANGO_INTERNAL_BASE_URL"
_ENV_TIMEOUT_SECONDS = "DJANGO_CLIENT_TIMEOUT_SECONDS"
_ENV_MAX_RETRIES = "DJANGO_CLIENT_MAX_RETRIES"
_ENV_RETRY_BACKOFF_SECONDS = "DJANGO_CLIENT_RETRY_BACKOFF_SECONDS"

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 0.25

_TRANSIENT_STATUS_CODES = frozenset({502, 503, 504})


def _read_env_float(name: str, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None or not str(raw_value).strip():
        return default
    return float(raw_value)


def _read_env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None or not str(raw_value).strip():
        return default
    return int(raw_value)


def normalize_base_url(base_url: str) -> str:
    """Strip trailing slashes so endpoint paths join predictably."""
    return base_url.rstrip("/")


def join_url(base_url: str, path: str) -> str:
    """Join a normalized base URL with an endpoint path."""
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{normalize_base_url(base_url)}{normalized_path}"


def _safe_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Django API returned HTTP {response.status_code}."

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail

    return f"Django API returned HTTP {response.status_code}."


class DjangoClient:
    """Small HTTP client for Django internal APIs used by AI agent services."""

    def __init__(
        self,
        base_url: str | None = None,
        service_token: str | None = None,
        request_id: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        resolved_base_url = base_url or os.environ.get(_ENV_BASE_URL)
        if not resolved_base_url or not str(resolved_base_url).strip():
            raise ValueError(
                "Django base URL is required. Set DJANGO_INTERNAL_BASE_URL or pass base_url."
            )

        self.base_url = normalize_base_url(str(resolved_base_url).strip())
        self.service_token = service_token
        self.request_id = request_id
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else _read_env_float(_ENV_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS)
        )
        self.max_retries = (
            max_retries
            if max_retries is not None
            else _read_env_int(_ENV_MAX_RETRIES, DEFAULT_MAX_RETRIES)
        )
        self.retry_backoff_seconds = (
            retry_backoff_seconds
            if retry_backoff_seconds is not None
            else _read_env_float(
                _ENV_RETRY_BACKOFF_SECONDS, DEFAULT_RETRY_BACKOFF_SECONDS
            )
        )
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(
            timeout=httpx.Timeout(self.timeout_seconds)
        )

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def __enter__(self) -> DjangoClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.service_token:
            headers["Authorization"] = f"Bearer {self.service_token}"
        if self.request_id:
            headers["X-Request-ID"] = self.request_id
        return headers

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params, json_body=None, retry=True)

    def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        retry: bool = False,
    ) -> dict[str, Any]:
        """POST JSON to Django.

        Retries are disabled by default because POST requests may be non-idempotent.
        Pass ``retry=True`` only when the caller knows a retry is safe.
        """
        return self._request("POST", path, params=None, json_body=json, retry=retry)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        json_body: dict[str, Any] | None,
        retry: bool,
    ) -> dict[str, Any]:
        url = join_url(self.base_url, path)
        headers = self._build_headers()
        attempt = 0

        while True:
            try:
                response = self._http_client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                if retry and attempt < self.max_retries:
                    self._sleep_before_retry(attempt)
                    attempt += 1
                    continue
                raise DjangoTimeoutError(
                    f"Django API request timed out after {self.timeout_seconds} seconds."
                ) from exc
            except httpx.ConnectError as exc:
                if retry and attempt < self.max_retries:
                    self._sleep_before_retry(attempt)
                    attempt += 1
                    continue
                raise DjangoConnectionError(
                    "Unable to connect to the Django API."
                ) from exc

            if (
                retry
                and response.status_code in _TRANSIENT_STATUS_CODES
                and attempt < self.max_retries
            ):
                self._sleep_before_retry(attempt)
                attempt += 1
                continue

            if response.status_code < 200 or response.status_code >= 300:
                raise DjangoHTTPError(
                    response.status_code,
                    _safe_error_message(response),
                )

            return self._parse_json(response)

    def _sleep_before_retry(self, attempt: int) -> None:
        delay = self.retry_backoff_seconds * (2**attempt)
        time.sleep(delay)

    def _parse_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise DjangoJSONError(
                f"Invalid JSON response from Django API (HTTP {response.status_code})."
            ) from exc

        if not isinstance(payload, dict):
            raise DjangoJSONError(
                f"Expected JSON object from Django API (HTTP {response.status_code})."
            )
        return payload
