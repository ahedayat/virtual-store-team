"""Unit tests for Sales Agent schema validation before return (Step 7.3)."""

from __future__ import annotations

import json
import os
import unittest
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from agents.sales.analysis import run_sales_analysis
from agents.sales.app.main import app
from agents.sales.validation import (
    SalesLLMOutputError,
    ensure_valid_sales_analysis_result,
    parse_llm_json_output,
    validate_sales_analysis_output,
)
from agents.shared.schemas import AgentSchemaValidationError, SalesAnalysisResult

EMPTY_CONTEXT_BUNDLE = {
    "report_run_id": "run-empty-1",
    "sales_summary": {
        "currency": "USD",
        "today": {
            "order_count": 0,
            "total_revenue": 0,
            "top_products": [],
        },
        "last_7_days": {
            "order_count": 0,
            "total_revenue": "0.00",
            "top_products": [],
        },
    },
}

NON_EMPTY_CONTEXT = {
    "sales_summary": {
        "today": {
            "order_count": 5,
            "total_revenue": "250.00",
            "top_products": [{"sku": "SKU-1", "revenue": "250.00"}],
        },
        "last_7_days": {
            "order_count": 0,
            "total_revenue": 0,
            "top_products": [],
        },
    },
}


def build_valid_sales_analysis_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "metadata": {
            "agent_name": "sales-agent",
            "report_run_id": "run-valid-1",
        },
        "summary": "Sales momentum is positive.",
        "insights": ["Top SKU performed well."],
        "recommendations": [
            {
                "priority": 2,
                "action_type": "sales.restock",
                "title": "Restock SKU-1",
                "description": "Inventory is low for a strong seller.",
                "rationale": "Recent order velocity exceeds available stock.",
                "payload": {"sku": "SKU-1", "current_stock": 2},
            }
        ],
        "warnings": [],
    }
    payload.update(overrides)
    return payload


class _JsonMockLLMProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.called = False

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.called = True
        return json.dumps(self.payload)


class _DictMockLLMProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return self.payload


class _MalformedJsonLLMProvider:
    def complete(self, messages: list[dict[str, str]]) -> str:
        return "{not valid json"


class SalesSchemaValidationTests(unittest.TestCase):
    def test_valid_sales_agent_output_passes_validation(self) -> None:
        payload = build_valid_sales_analysis_payload()

        validated = validate_sales_analysis_output(payload)

        self.assertIsInstance(validated, SalesAnalysisResult)
        self.assertEqual(validated.summary, payload["summary"])
        self.assertEqual(len(validated.recommendations), 1)
        self.assertEqual(validated.recommendations[0].action_type, "sales.restock")

    def test_missing_required_recommendation_field_fails_validation(self) -> None:
        payload = build_valid_sales_analysis_payload()
        del payload["recommendations"][0]["rationale"]

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_sales_analysis_output(payload)

        error = ctx.exception
        self.assertEqual(error.schema_name, "SalesAnalysisResult")
        self.assertTrue(
            any("rationale" in item["field"] for item in error.field_errors)
        )

    def test_invalid_action_type_fails_validation(self) -> None:
        payload = build_valid_sales_analysis_payload()
        payload["recommendations"][0]["action_type"] = "sales.promote"

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_sales_analysis_output(payload)

        self.assertTrue(
            any("action_type" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_priority_below_one_fails_validation(self) -> None:
        payload = build_valid_sales_analysis_payload()
        payload["recommendations"][0]["priority"] = 0

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_sales_analysis_output(payload)

        self.assertTrue(
            any("priority" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_priority_above_five_fails_validation(self) -> None:
        payload = build_valid_sales_analysis_payload()
        payload["recommendations"][0]["priority"] = 6

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_sales_analysis_output(payload)

        self.assertTrue(
            any("priority" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_extra_unknown_fields_are_rejected(self) -> None:
        payload = build_valid_sales_analysis_payload(extra_field="forbidden")

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_sales_analysis_output(payload)

        self.assertTrue(
            any(item["field"] == "extra_field" for item in ctx.exception.field_errors)
        )

    def test_malformed_llm_json_is_handled_safely(self) -> None:
        with self.assertRaises(SalesLLMOutputError) as ctx:
            parse_llm_json_output("{not valid json")

        self.assertIn("malformed JSON", str(ctx.exception))

    def test_non_object_json_is_rejected(self) -> None:
        with self.assertRaises(SalesLLMOutputError):
            parse_llm_json_output('["not", "an", "object"]')

    def test_mock_provider_dict_output_is_parsed_directly(self) -> None:
        payload = build_valid_sales_analysis_payload()

        parsed = parse_llm_json_output(payload)

        validated = ensure_valid_sales_analysis_result(parsed)
        self.assertEqual(validated.summary, payload["summary"])

    def test_empty_sales_fallback_passes_validation(self) -> None:
        result = run_sales_analysis(
            context=EMPTY_CONTEXT_BUNDLE,
            report_run_id="run-empty-1",
            output_language="en",
        )

        self.assertIsInstance(result, SalesAnalysisResult)
        self.assertEqual(result.recommendations, [])

    def test_run_sales_analysis_uses_default_mock_provider(self) -> None:
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False):
            result = run_sales_analysis(
                context=NON_EMPTY_CONTEXT,
                report_run_id="run-default-mock-1",
                output_language="en",
            )

        self.assertEqual(result.metadata.agent_name, "sales-agent")
        self.assertGreaterEqual(len(result.recommendations), 1)

    def test_run_sales_analysis_validates_mock_llm_output(self) -> None:
        provider = _JsonMockLLMProvider(build_valid_sales_analysis_payload())

        result = run_sales_analysis(
            context=NON_EMPTY_CONTEXT,
            report_run_id="run-valid-1",
            output_language="en",
            llm_provider=provider,
        )

        self.assertTrue(provider.called)
        self.assertEqual(result.metadata.report_run_id, "run-valid-1")
        self.assertEqual(len(result.recommendations), 1)

    def test_run_sales_analysis_rejects_invalid_mock_llm_output(self) -> None:
        payload = build_valid_sales_analysis_payload()
        payload["recommendations"][0]["action_type"] = "sales.promote"
        provider = _JsonMockLLMProvider(payload)

        with self.assertRaises(AgentSchemaValidationError):
            run_sales_analysis(
                context=NON_EMPTY_CONTEXT,
                report_run_id="run-invalid-1",
                llm_provider=provider,
            )

    def test_run_sales_analysis_rejects_malformed_mock_llm_json(self) -> None:
        with self.assertRaises(SalesLLMOutputError):
            run_sales_analysis(
                context=NON_EMPTY_CONTEXT,
                report_run_id="run-malformed-1",
                llm_provider=_MalformedJsonLLMProvider(),
            )

    def test_dict_mock_provider_output_uses_same_validation_path(self) -> None:
        provider = _DictMockLLMProvider(build_valid_sales_analysis_payload())

        result = run_sales_analysis(
            context=NON_EMPTY_CONTEXT,
            report_run_id="run-dict-mock-1",
            llm_provider=provider,
        )

        self.assertEqual(result.metadata.agent_name, "sales-agent")

    @patch("agents.sales.analysis.log_sales_validation_failure")
    def test_validation_failure_logs_safe_summary_only(
        self,
        mock_log_failure,
    ) -> None:
        payload = build_valid_sales_analysis_payload()
        payload["recommendations"][0]["priority"] = 9
        provider = _JsonMockLLMProvider(payload)

        with self.assertRaises(AgentSchemaValidationError):
            run_sales_analysis(
                context=NON_EMPTY_CONTEXT,
                report_run_id="run-log-1",
                request_id="req-log-1",
                llm_provider=provider,
            )

        mock_log_failure.assert_called_once()
        logged_exc = mock_log_failure.call_args.args[0]
        self.assertIsInstance(logged_exc, AgentSchemaValidationError)
        self.assertEqual(
            mock_log_failure.call_args.kwargs["report_run_id"],
            "run-log-1",
        )
        self.assertEqual(
            mock_log_failure.call_args.kwargs["request_id"],
            "req-log-1",
        )
        self.assertNotIn("customer", str(logged_exc).lower())


class SalesRunEndpointValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_run_endpoint_returns_validated_empty_sales_output(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "context": EMPTY_CONTEXT_BUNDLE,
                "report_run_id": "run-empty-1",
                "output_language": "en",
            },
            headers={"X-Request-ID": "trace-123"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metadata"]["agent_name"], "sales-agent")
        self.assertEqual(body["recommendations"], [])
        self.assertEqual(body["summary"], "No sales were recorded for this period.")

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    def test_run_endpoint_returns_mock_output_for_non_empty_sales(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "context": NON_EMPTY_CONTEXT,
                "report_run_id": "run-non-empty-1",
                "output_language": "en",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metadata"]["agent_name"], "sales-agent")
        self.assertGreaterEqual(len(body["recommendations"]), 1)

    @patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=False)
    def test_run_endpoint_returns_501_for_unimplemented_provider(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "context": NON_EMPTY_CONTEXT,
                "report_run_id": "run-non-empty-1",
            },
        )

        self.assertEqual(response.status_code, 501)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "not_implemented")

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_does_not_expose_stack_traces(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "context": NON_EMPTY_CONTEXT,
                "report_run_id": "run-non-empty-2",
            },
        )

        body_text = json.dumps(response.json())
        self.assertNotIn("Traceback", body_text)
        self.assertNotIn('File "', body_text)

    @patch("agents.sales.app.main.run_sales_analysis")
    def test_run_endpoint_maps_validation_errors_to_422(
        self,
        mock_run_sales_analysis,
    ) -> None:
        mock_run_sales_analysis.side_effect = AgentSchemaValidationError(
            "Agent response failed validation against schema 'SalesAnalysisResult': "
            "recommendations[0].priority: Input should be less than or equal to 5",
            schema_name="SalesAnalysisResult",
            field_errors=[
                {
                    "field": "recommendations[0].priority",
                    "message": "Input should be less than or equal to 5",
                    "type": "less_than_equal",
                }
            ],
        )

        response = self.client.post(
            "/run",
            json={
                "context": EMPTY_CONTEXT_BUNDLE,
                "report_run_id": "run-invalid-1",
            },
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "schema_validation_failed")
        self.assertEqual(detail["schema_name"], "SalesAnalysisResult")
        self.assertIn("field_errors", detail)
        self.assertNotIn("Traceback", json.dumps(detail))


if __name__ == "__main__":
    unittest.main()
