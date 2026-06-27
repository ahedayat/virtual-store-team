"""DB-backed Phase 10 E2E harness: real coordinator workflow + Django live server."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from agents.coordinator.app.schemas import DailyReportJobRequest
from agents.coordinator.app.workflow_endpoint import (
    build_workflow_response,
    build_workflow_state_from_request,
    extract_bearer_token,
)
from agents.coordinator.config import CoordinatorNodeTimeouts
from agents.coordinator.nodes import WorkflowNodeDependencies
from agents.coordinator.runner import run_daily_report_workflow
from agents.coordinator.tests.integration_harness import (
    CONTENT_HOST,
    SALES_HOST,
    SUPPORT_HOST,
    ServiceRouterTransport,
    build_integration_http_client,
    build_integration_specialist_client,
)
from agents.shared.django_client import DjangoClient
from operations.tests.mock_coordinator_server import MockCoordinatorServer

_SPECIALIST_HOSTS = frozenset({SALES_HOST, CONTENT_HOST, SUPPORT_HOST})


class E2ECompositeTransport(httpx.BaseTransport):
    """Route specialist calls in-process; forward Django calls to the live test server."""

    def __init__(
        self,
        *,
        specialist_transport: ServiceRouterTransport,
        django_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._specialist_transport = specialist_transport
        self._django_transport = django_transport or httpx.HTTPTransport()
        self._request_lock = threading.Lock()
        self.request_log: list[dict[str, str]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        with self._request_lock:
            host = request.url.host
            path = request.url.path
            method = request.method
            self.request_log.append({"host": host, "path": path, "method": method})

            if host in _SPECIALIST_HOSTS:
                return self._specialist_transport.handle_request(request)
            return self._django_transport.handle_request(request)


@dataclass
class Phase10WorkflowDeps:
    transport: E2ECompositeTransport
    specialist_transport: ServiceRouterTransport
    deps: WorkflowNodeDependencies


def build_phase10_workflow_deps(
    *,
    django_base_url: str,
    transport_factory: Callable[[], ServiceRouterTransport],
    node_timeouts: CoordinatorNodeTimeouts | None = None,
) -> Phase10WorkflowDeps:
    specialist_transport = transport_factory()
    composite = E2ECompositeTransport(specialist_transport=specialist_transport)
    http_client = build_integration_http_client(composite)

    def specialist_factory(timeout_seconds: float):
        return build_integration_specialist_client(
            http_client,
            timeout_seconds=timeout_seconds,
        )

    django_client = DjangoClient(
        base_url=django_base_url,
        http_client=http_client,
    )

    deps = WorkflowNodeDependencies(
        django_client=django_client,
        specialist_client_factory=specialist_factory,
        node_timeouts=node_timeouts,
    )
    return Phase10WorkflowDeps(
        transport=composite,
        specialist_transport=specialist_transport,
        deps=deps,
    )


class WorkflowCoordinatorBridgeServer(MockCoordinatorServer):
    """Mock coordinator HTTP server that runs the real LangGraph-backed workflow."""

    def __init__(
        self,
        *,
        django_base_url: str,
        transport_factory: Callable[[], ServiceRouterTransport],
        node_timeouts: CoordinatorNodeTimeouts | None = None,
    ) -> None:
        self.django_base_url = django_base_url
        self._transport_factory = transport_factory
        self._node_timeouts = node_timeouts
        self.last_workflow_deps: Phase10WorkflowDeps | None = None
        super().__init__(on_request=self._run_workflow)

    def _run_workflow(self, payload: dict[str, Any]) -> None:
        request = self.requests[-1]
        body_text = request.get("body", "")
        parsed_body = json.loads(body_text) if body_text else {}
        if not isinstance(parsed_body, dict):
            parsed_body = {}

        auth_header = request.get("headers", {}).get("Authorization")
        service_token = extract_bearer_token(auth_header)
        request_id = request.get("headers", {}).get("X-Request-ID")

        workflow_deps = build_phase10_workflow_deps(
            django_base_url=self.django_base_url,
            transport_factory=self._transport_factory,
            node_timeouts=self._node_timeouts,
        )
        workflow_deps.deps.django_client.service_token = service_token
        workflow_deps.deps.django_client.request_id = request_id
        self.last_workflow_deps = workflow_deps

        job_request = DailyReportJobRequest.model_validate(parsed_body)
        state = build_workflow_state_from_request(
            job_request,
            service_token=service_token,
            request_id=request_id,
        )
        try:
            result_state = run_daily_report_workflow(state, workflow_deps.deps)
        except Exception as exc:
            self.set_json_response(
                {
                    "status": "failed",
                    "workflow": "daily_report",
                    "report_run_id": str(job_request.report_run_id),
                    "message": f"{type(exc).__name__}: {exc}",
                    "warnings": [],
                    "partial": False,
                }
            )
            return
        response = build_workflow_response(job_request, result_state)
        self.set_json_response(response.model_dump(mode="json"))
