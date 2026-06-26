"""Tests for coordinator-agent daily report stub endpoint."""

import json
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from agents.coordinator.app.main import STUB_MESSAGE, STUB_WARNING, app

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


class CoordinatorDailyReportStubTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_returns_ok(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "coordinator-agent"},
        )

    def test_daily_report_stub_accepts_valid_phase5_payload(self) -> None:
        response = self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "accepted")
        self.assertEqual(body["workflow"], "daily_report")
        self.assertEqual(body["report_run_id"], VALID_REPORT_RUN_ID)
        self.assertEqual(body["message"], STUB_MESSAGE)
        self.assertEqual(len(body["warnings"]), 1)
        self.assertEqual(body["warnings"][0]["code"], STUB_WARNING.code)
        self.assertEqual(body["warnings"][0]["message"], STUB_WARNING.message)

    def test_daily_report_stub_response_is_deterministic(self) -> None:
        first = self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(),
        ).json()
        second = self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(),
        ).json()

        self.assertEqual(first, second)

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

    def test_bearer_authorization_header_is_accepted(self) -> None:
        response = self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(),
            headers={"Authorization": "Bearer test-service-jwt"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "accepted")

    def test_request_without_authorization_is_accepted(self) -> None:
        response = self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(),
        )

        self.assertEqual(response.status_code, 200)

    def test_non_bearer_authorization_returns_401(self) -> None:
        response = self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(),
            headers={"Authorization": "Token not-bearer"},
        )

        self.assertEqual(response.status_code, 401)

    def test_x_request_id_header_is_accepted(self) -> None:
        response = self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(request_id="req-123"),
            headers={"X-Request-ID": "trace-abc"},
        )

        self.assertEqual(response.status_code, 200)

    def test_response_does_not_expose_authorization_token(self) -> None:
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
        response = self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(requested_by="manager@example.com"),
        )

        body = response.json()
        self.assertNotIn("requested_by", body)
        self.assertNotIn("manager@example.com", json.dumps(body))

    @patch("agents.coordinator.app.main.logger")
    def test_logger_does_not_receive_raw_token(self, mock_logger) -> None:
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

    def test_stub_warning_indicates_no_real_orchestration(self) -> None:
        response = self.client.post(
            "/workflows/daily-report",
            json=build_valid_payload(),
        )

        warnings = response.json()["warnings"]
        self.assertTrue(
            any(item["code"] == "stub_mode" for item in warnings),
            "Expected stub_mode warning in response.",
        )


if __name__ == "__main__":
    unittest.main()
