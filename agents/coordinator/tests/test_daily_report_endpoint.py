"""Tests for coordinator-agent daily report workflow endpoint (Step 10.5)."""

from __future__ import annotations

import json
import os
import unittest
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from agents.coordinator.app.main import app
from agents.coordinator.app.workflow_endpoint import (
    COMPLETED_MESSAGE,
    FAILED_MESSAGE,
    build_workflow_state_from_request,
    execute_daily_report_workflow,
)
from agents.coordinator.state import DailyReportWorkflowState
from agents.shared.schemas.base import AgentWarning

VALID_REPORT_RUN_ID = "11111111-1111-4111-8111-111111111111"
VALID_TENANT_ID = "22222222-2222-4222-8222-222222222222"
VALID_STORE_ID = "33333333-3333-4333-8333-333333333333"


def build_valid_payload(**overrides: object) -> dict[str, object]:
    payload = {
        "report_run_id": VALID_REPORT_RUN_ID,
        "tenant_id": VALID_TENANT_ID,
        "store_id": VALID_STORE_ID,
        "context_ref": {
            "type": "report_run",
            "id": VALID_REPORT_RUN_ID,
        },
    }
    payload.update(overrides)
    return payload


class CoordinatorDailyReportEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_returns_ok(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "coordinator-agent"},
        )

    @patch("agents.coordinator.app.main.execute_daily_report_workflow")
    def test_endpoint_invokes_real_workflow_runner(self, mock_execute) -> None:
        mock_execute.return_value = MagicMock(
            status="completed",
            workflow="daily_report",
            report_run_id=VALID_REPORT_RUN_ID,
            message=COMPLETED_MESSAGE,
            warnings=[],
            partial=False,
        )

        response = self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(),
            headers={
                "Authorization": "Bearer test-service-jwt",
                "X-Request-ID": "trace-abc",
            },
        )

        self.assertEqual(response.status_code, 200)
        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args.kwargs
        self.assertEqual(call_kwargs["service_token"], "test-service-jwt")
        self.assertEqual(call_kwargs["request_id"], "trace-abc")

    def test_request_payload_maps_into_workflow_state(self) -> None:
        from agents.coordinator.app.schemas import DailyReportJobRequest

        payload = DailyReportJobRequest.model_validate(build_valid_payload(request_id="req-body"))
        state = build_workflow_state_from_request(
            payload,
            service_token="coord-jwt",
            request_id="trace-header",
        )

        self.assertEqual(state.report_run_id, VALID_REPORT_RUN_ID)
        self.assertEqual(state.tenant_id, VALID_TENANT_ID)
        self.assertEqual(state.store_id, VALID_STORE_ID)
        self.assertEqual(state.service_token, "coord-jwt")
        self.assertEqual(state.request_id, "trace-header")

    @patch("agents.coordinator.app.workflow_endpoint.run_daily_report_workflow")
    def test_successful_endpoint_returns_completed_response(self, mock_run) -> None:
        mock_run.return_value = DailyReportWorkflowState(
            report_run_id=VALID_REPORT_RUN_ID,
            tenant_id=VALID_TENANT_ID,
            store_id=VALID_STORE_ID,
            status="completed",
            merged_report={"partial": False},
        )
        from agents.coordinator.app.schemas import DailyReportJobRequest

        payload = DailyReportJobRequest.model_validate(build_valid_payload())
        response = execute_daily_report_workflow(
            payload,
            service_token="service-jwt",
            request_id="req-1",
        )

        self.assertEqual(response.status, "completed")
        self.assertEqual(response.workflow, "daily_report")
        self.assertEqual(response.report_run_id, VALID_REPORT_RUN_ID)
        self.assertEqual(response.message, COMPLETED_MESSAGE)
        self.assertFalse(response.partial)
        mock_run.assert_called_once()
        passed_state = mock_run.call_args.args[0]
        self.assertEqual(passed_state.service_token, "service-jwt")
        self.assertEqual(passed_state.request_id, "req-1")

    @patch("agents.coordinator.app.workflow_endpoint.run_daily_report_workflow")
    def test_workflow_failure_returns_sanitized_failed_response(self, mock_run) -> None:
        mock_run.return_value = DailyReportWorkflowState(
            report_run_id=VALID_REPORT_RUN_ID,
            tenant_id=VALID_TENANT_ID,
            store_id=VALID_STORE_ID,
            failed=True,
            status="failed",
            error_message="Context fetch timed out.",
            warnings=[
                AgentWarning(
                    code="critical_node_timeout",
                    message="Context fetch timed out.",
                )
            ],
        )
        from agents.coordinator.app.schemas import DailyReportJobRequest

        payload = DailyReportJobRequest.model_validate(build_valid_payload())
        response = execute_daily_report_workflow(payload, service_token=None, request_id=None)

        self.assertEqual(response.status, "failed")
        self.assertEqual(response.message, "Context fetch timed out.")
        self.assertEqual(response.warnings[0].code, "critical_node_timeout")
        response_text = json.dumps(response.model_dump())
        self.assertNotIn("Bearer", response_text)

    @patch("agents.coordinator.app.workflow_endpoint.run_daily_report_workflow")
    def test_unexpected_exception_returns_sanitized_failed_response(self, mock_run) -> None:
        mock_run.side_effect = RuntimeError("raw internal failure details")
        from agents.coordinator.app.schemas import DailyReportJobRequest

        payload = DailyReportJobRequest.model_validate(build_valid_payload())
        response = execute_daily_report_workflow(payload, service_token=None, request_id=None)

        self.assertEqual(response.status, "failed")
        self.assertEqual(response.message, "Daily report workflow failed unexpectedly.")
        self.assertNotIn("raw internal failure details", response.message)

    @patch("agents.coordinator.app.main.execute_daily_report_workflow")
    def test_endpoint_prefers_header_request_id_over_body(self, mock_execute) -> None:
        mock_execute.return_value = MagicMock(
            status="completed",
            workflow="daily_report",
            report_run_id=VALID_REPORT_RUN_ID,
            message=COMPLETED_MESSAGE,
            warnings=[],
            partial=False,
        )

        self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(request_id="body-req"),
            headers={"X-Request-ID": "header-req"},
        )

        self.assertEqual(mock_execute.call_args.kwargs["request_id"], "header-req")

    def test_missing_report_run_id_returns_validation_error(self) -> None:
        payload = build_valid_payload()
        del payload["report_run_id"]

        response = self.client.post("/workflows/daily-report", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertIn("detail", response.json())

    def test_invalid_context_ref_type_fails_validation(self) -> None:
        payload = build_valid_payload(
            context_ref={
                "type": "store",
                "id": VALID_REPORT_RUN_ID,
            }
        )

        response = self.client.post("/workflows/daily-report", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_context_ref_id_mismatch_fails_validation(self) -> None:
        payload = build_valid_payload(
            context_ref={
                "type": "report_run",
                "id": str(uuid.uuid4()),
            }
        )

        response = self.client.post("/workflows/daily-report", json=payload)

        self.assertEqual(response.status_code, 422)

    def test_non_bearer_authorization_returns_401(self) -> None:
        response = self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(),
            headers={"Authorization": "Token not-bearer"},
        )

        self.assertEqual(response.status_code, 401)

    def test_response_does_not_expose_authorization_token(self) -> None:
        with patch(
            "agents.coordinator.app.main.execute_daily_report_workflow",
            return_value=MagicMock(
                status="completed",
                workflow="daily_report",
                report_run_id=VALID_REPORT_RUN_ID,
                message=COMPLETED_MESSAGE,
                warnings=[],
                partial=False,
            ),
        ):
            token = "Bearer super-secret-service-jwt-value"
            response = self.client.post(
                "/workflows/daily-report",
                json=build_valid_payload(),
                headers={"Authorization": token},
            )

        response_text = json.dumps(response.json())
        self.assertNotIn("super-secret-service-jwt-value", response_text)
        self.assertNotIn(token, response_text)

    def test_response_does_not_include_pii_fields(self) -> None:
        with patch(
            "agents.coordinator.app.main.execute_daily_report_workflow",
            return_value=MagicMock(
                status="completed",
                workflow="daily_report",
                report_run_id=VALID_REPORT_RUN_ID,
                message=COMPLETED_MESSAGE,
                warnings=[],
                partial=False,
            ),
        ):
            response = self.client.post(
                "/workflows/daily-report",
                json=build_valid_payload(requested_by="manager@example.com"),
            )

        body = response.json()
        self.assertNotIn("requested_by", body)
        self.assertNotIn("manager@example.com", json.dumps(body))

    @patch("agents.coordinator.app.workflow_endpoint.logger")
    @patch("agents.coordinator.app.main.execute_daily_report_workflow")
    def test_logger_does_not_receive_raw_token(self, mock_execute, mock_logger) -> None:
        mock_execute.return_value = MagicMock(
            status="completed",
            workflow="daily_report",
            report_run_id=VALID_REPORT_RUN_ID,
            message=COMPLETED_MESSAGE,
            warnings=[],
            partial=False,
        )
        token = "Bearer raw-token-should-not-log"
        self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(),
            headers={"Authorization": token},
        )

        for call in mock_logger.info.call_args_list:
            logged_extra = call.kwargs.get("extra", {})
            self.assertNotIn("authorization", logged_extra)
            self.assertNotIn("raw-token-should-not-log", str(call))

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    @patch("agents.coordinator.app.workflow_endpoint.run_daily_report_workflow")
    def test_endpoint_runs_workflow_without_stub_warning(self, mock_run) -> None:
        mock_run.return_value = DailyReportWorkflowState(
            report_run_id=VALID_REPORT_RUN_ID,
            tenant_id=VALID_TENANT_ID,
            store_id=VALID_STORE_ID,
            status="completed",
            merged_report={"partial": True},
            warnings=[
                AgentWarning(
                    code="specialist_node_timeout",
                    message="Support specialist timed out.",
                )
            ],
        )

        response = self.client.post("/workflows/daily-report", json=build_valid_payload())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "completed")
        self.assertTrue(body["partial"])
        self.assertFalse(any(item["code"] == "stub_mode" for item in body["warnings"]))


if __name__ == "__main__":
    unittest.main()
