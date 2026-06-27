"""Test harness for coordinator full-graph integration (Step 10.4)."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import httpx
from fastapi.testclient import TestClient

from agents.content.app.main import app as content_app
from agents.coordinator.topology import SpecialistAgentName
from agents.sales.app.main import app as sales_app
from agents.support.app.main import app as support_app

VALID_REPORT_RUN_ID = "11111111-1111-4111-8111-111111111111"
VALID_TENANT_ID = "22222222-2222-4222-8222-222222222222"
VALID_STORE_ID = "33333333-3333-4333-8333-333333333333"
VALID_PRODUCT_ID = "44444444-4444-4444-8444-444444444444"

SALES_HOST = "sales.test"
CONTENT_HOST = "content.test"
SUPPORT_HOST = "support.test"
DJANGO_HOST = "django.test"

SPECIALIST_BASE_URLS = {
    SpecialistAgentName.SALES: f"http://{SALES_HOST}:8101",
    SpecialistAgentName.CONTENT: f"http://{CONTENT_HOST}:8102",
    SpecialistAgentName.SUPPORT: f"http://{SUPPORT_HOST}:8103",
}

INTEGRATION_CONTEXT_BUNDLE: dict[str, Any] = {
    "report_run_id": VALID_REPORT_RUN_ID,
    "generated_at": "2026-06-27T12:00:00+00:00",
    "period": {
        "from": "2026-06-26T00:00:00+00:00",
        "to": "2026-06-27T00:00:00+00:00",
    },
    "tenant": {
        "id": VALID_TENANT_ID,
        "slug": "tenant-a",
        "name": "Tenant A",
    },
    "store": {
        "id": VALID_STORE_ID,
        "slug": "store-a",
        "name": "Demo Store",
        "timezone": "UTC",
        "currency": "USD",
        "settings": {"brand_voice": {"tone": "warm"}},
    },
    "products": {
        "count": 1,
        "items": [
            {
                "product_id": VALID_PRODUCT_ID,
                "title": "Canvas Tote",
                "category": "Bags",
                "sku": "TOTE-001",
            }
        ],
    },
    "sales_summary": {
        "currency": "USD",
        "today": {
            "order_count": 5,
            "total_revenue": "250.00",
            "top_products": [{"sku": "TOTE-001", "revenue": "250.00"}],
        },
        "last_7_days": {
            "order_count": 12,
            "total_revenue": "1200.00",
            "top_products": [{"sku": "TOTE-001", "revenue": "1200.00"}],
        },
    },
    "inventory": {
        "low_stock_count": 1,
        "items": [
            {
                "product_id": VALID_PRODUCT_ID,
                "sku": "TOTE-001",
                "available_quantity": 2,
                "low_stock_threshold": 5,
            }
        ],
    },
    "messages": {
        "thread_count": 1,
        "threads": [
            {
                "thread_ref": "thread-1",
                "channel": "instagram_dm",
                "messages": [
                    {
                        "message_ref": "msg-1",
                        "sender_role": "customer",
                        "text": "What are your store hours?",
                    }
                ],
            }
        ],
    },
    "warnings": [],
}


class RecordingDjangoState:
    """Mutable Django API call log for integration assertions."""

    def __init__(self) -> None:
        self.context_calls: list[str] = []
        self.agent_output_calls: list[dict[str, Any]] = []
        self.action_calls: list[dict[str, Any]] = []
        self.complete_calls: list[dict[str, Any]] = []
        self._agent_output_counter = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body = self._read_json_body(request)

        if path == f"/internal/ai/context/{VALID_REPORT_RUN_ID}/":
            self.context_calls.append(path)
            return httpx.Response(200, json=INTEGRATION_CONTEXT_BUNDLE)

        if path == "/internal/ai/agent-outputs/":
            self.agent_output_calls.append(body)
            self._agent_output_counter += 1
            return httpx.Response(
                201,
                json={
                    "id": f"aaaaaaaa-aaaa-4aaa-8aaa-{self._agent_output_counter:012d}",
                    "agent_name": "coordinator-agent",
                    "output_type": body.get("output_type"),
                    "report_run_id": body.get("report_run_id"),
                },
            )

        if path == "/internal/ai/actions/":
            self.action_calls.append(body)
            return httpx.Response(
                201,
                json={
                    "id": str(uuid.uuid4()),
                    "status": "pending_approval",
                    "action_type": body.get("action_type"),
                },
            )

        if path == f"/internal/ai/report-runs/{VALID_REPORT_RUN_ID}/complete/":
            self.complete_calls.append(body)
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "report_run_id": VALID_REPORT_RUN_ID,
                    "daily_report_id": str(uuid.uuid4()),
                    "completed_at": "2026-06-27T12:05:00+00:00",
                },
            )

        return httpx.Response(404, json={"detail": "Not found."})

    @staticmethod
    def _read_json_body(request: httpx.Request) -> dict[str, Any]:
        raw = request.content.decode("utf-8") if request.content else ""
        if not raw:
            return {}
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}


class _SpecialistTestClientBridge:
    """Bridge sync FastAPI TestClient responses into httpx transport handlers."""

    def __init__(self, app: Any) -> None:
        self._client = TestClient(app)

    def post_run(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8")) if request.content else {}
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() in {"authorization", "x-request-id", "content-type", "accept"}
        }
        response = self._client.post("/run", json=body, headers=headers)
        try:
            payload = response.json()
        except ValueError:
            payload = {"detail": response.text}
        return httpx.Response(response.status_code, json=payload)


class ServiceRouterTransport(httpx.BaseTransport):
    """Route HTTP requests to in-process specialist apps or Django mock."""

    def __init__(
        self,
        *,
        django_state: RecordingDjangoState | None = None,
        support_delay_seconds: float = 0.0,
        support_status_code: int | None = None,
        content_delay_seconds: float = 0.0,
        content_status_code: int | None = None,
    ) -> None:
        self.django_state = django_state or RecordingDjangoState()
        self.request_log: list[dict[str, str]] = []
        self.specialist_run_bodies: list[dict[str, Any]] = []
        self._sales_bridge = _SpecialistTestClientBridge(sales_app)
        self._content_bridge = _SpecialistTestClientBridge(content_app)
        self._support_bridge = _SpecialistTestClientBridge(support_app)
        self._support_delay_seconds = support_delay_seconds
        self._support_status_code = support_status_code
        self._content_delay_seconds = content_delay_seconds
        self._content_status_code = content_status_code

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path
        method = request.method
        self.request_log.append({"host": host, "path": path, "method": method})

        if host == DJANGO_HOST:
            return self.django_state.handle_request(request)

        if host == SALES_HOST and path == "/run" and method == "POST":
            self._capture_run_body(request)
            return self._sales_bridge.post_run(request)
        if host == CONTENT_HOST and path == "/run" and method == "POST":
            self._capture_run_body(request)
            if self._content_status_code is not None:
                return httpx.Response(
                    self._content_status_code,
                    json={"detail": "Simulated specialist failure."},
                )
            if self._content_delay_seconds > 0:
                time.sleep(self._content_delay_seconds)
            return self._content_bridge.post_run(request)
        if host == SUPPORT_HOST and path == "/run" and method == "POST":
            self._capture_run_body(request)
            if self._support_status_code is not None:
                return httpx.Response(
                    self._support_status_code,
                    json={"detail": "Simulated specialist failure."},
                )
            if self._support_delay_seconds > 0:
                time.sleep(self._support_delay_seconds)
            return self._support_bridge.post_run(request)

        return httpx.Response(502, json={"detail": "Unknown downstream host."})

    def _capture_run_body(self, request: httpx.Request) -> None:
        raw = request.content.decode("utf-8") if request.content else ""
        if not raw:
            return
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            self.specialist_run_bodies.append(parsed)


def build_integration_http_client(
    transport: ServiceRouterTransport,
) -> httpx.Client:
    return httpx.Client(transport=transport, timeout=httpx.Timeout(30.0))


def build_integration_django_client(
    http_client: httpx.Client,
    *,
    service_token: str = "service-jwt",
    request_id: str = "integration-req-1",
) -> Any:
    from agents.shared.django_client import DjangoClient

    return DjangoClient(
        base_url=f"http://{DJANGO_HOST}:8000",
        service_token=service_token,
        request_id=request_id,
        http_client=http_client,
    )


def build_integration_specialist_client(
    http_client: httpx.Client,
    *,
    service_token: str = "service-jwt",
    request_id: str = "integration-req-1",
    timeout_seconds: float = 30.0,
) -> Any:
    from agents.coordinator.specialist_clients import SpecialistAgentClient

    return SpecialistAgentClient(
        service_token=service_token,
        request_id=request_id,
        timeout_seconds=timeout_seconds,
        http_client=http_client,
        base_urls=SPECIALIST_BASE_URLS,
    )
