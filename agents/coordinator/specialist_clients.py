"""HTTP client for coordinator-initiated specialist agent ``POST /run`` calls."""

from __future__ import annotations

from typing import Any

import httpx

from agents.coordinator.topology import (
    SpecialistAgentName,
    UnknownSpecialistAgentError,
    build_specialist_run_url,
    parse_specialist_agent_name,
)

__all__ = [
    "SpecialistAgentClient",
    "SpecialistAgentClientError",
    "SpecialistAgentHTTPError",
    "UnknownSpecialistAgentError",
]


class SpecialistAgentClientError(Exception):
    """Base error for coordinator specialist-agent HTTP client failures."""


class SpecialistAgentHTTPError(SpecialistAgentClientError):
    """Raised when a specialist agent returns a non-2xx HTTP response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"Specialist agent returned HTTP {status_code}: {message}")


class SpecialistAgentClient:
    """Prepare and execute coordinator-to-specialist ``POST /run`` requests.

    Only the coordinator workflow should use this client. Specialist agents
    must not call each other directly.
    """

    def __init__(
        self,
        *,
        service_token: str | None = None,
        request_id: str | None = None,
        timeout_seconds: float = 30.0,
        http_client: httpx.Client | None = None,
        base_urls: dict[SpecialistAgentName, str] | None = None,
    ) -> None:
        self.service_token = service_token
        self.request_id = request_id
        self.timeout_seconds = timeout_seconds
        self._base_urls = base_urls or {}
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds)
        )

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def __enter__(self) -> SpecialistAgentClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _resolve_base_url(self, agent_name: SpecialistAgentName) -> str | None:
        return self._base_urls.get(agent_name)

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

    def prepare_run_request(
        self,
        agent_name: SpecialistAgentName | str,
        payload: dict[str, Any],
        *,
        base_url: str | None = None,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        """Return ``(url, headers, json_body)`` without making an HTTP request."""
        parsed = (
            agent_name
            if isinstance(agent_name, SpecialistAgentName)
            else parse_specialist_agent_name(agent_name)
        )
        resolved_base_url = base_url or self._resolve_base_url(parsed)
        url = build_specialist_run_url(parsed, base_url=resolved_base_url)
        return url, self._build_headers(), payload

    def run_specialist(
        self,
        agent_name: SpecialistAgentName | str,
        payload: dict[str, Any],
        *,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """POST a run payload to a specialist agent ``/run`` endpoint."""
        url, headers, json_body = self.prepare_run_request(
            agent_name,
            payload,
            base_url=base_url,
        )

        try:
            response = self._http_client.post(url, json=json_body, headers=headers)
        except httpx.TimeoutException as exc:
            raise SpecialistAgentClientError(
                "Specialist agent request timed out."
            ) from exc
        except httpx.ConnectError as exc:
            raise SpecialistAgentClientError(
                "Unable to connect to specialist agent."
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise SpecialistAgentHTTPError(
                response.status_code,
                _safe_error_message(response),
            )

        return _parse_json_object(response)

    def run_sales(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.run_specialist(SpecialistAgentName.SALES, payload)

    def run_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.run_specialist(SpecialistAgentName.CONTENT, payload)

    def run_support(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.run_specialist(SpecialistAgentName.SUPPORT, payload)


def _safe_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Specialist agent returned HTTP {response.status_code}."

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail

    return f"Specialist agent returned HTTP {response.status_code}."


def _parse_json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise SpecialistAgentClientError(
            f"Invalid JSON response from specialist agent (HTTP {response.status_code})."
        ) from exc

    if not isinstance(payload, dict):
        raise SpecialistAgentClientError(
            f"Expected JSON object from specialist agent (HTTP {response.status_code})."
        )
    return payload
