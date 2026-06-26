import unittest
from enum import StrEnum

from pydantic import Field

from agents.shared.schemas import (
    AgentResponseMetadata,
    AgentSchemaConfigurationError,
    AgentSchemaValidationError,
    AgentWarning,
    BaseAgentResponse,
    export_json_schema,
    validate_agent_response,
)
from agents.shared.schemas.base import StrictAgentModel


class DummyStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"


class DummyAgentResult(StrictAgentModel):
    status: DummyStatus
    metadata: AgentResponseMetadata
    summary: str = ""


VALID_BASE_PAYLOAD = {
    "metadata": {
        "agent_name": "sales",
        "report_run_id": "run-123",
    },
    "warnings": [],
}


class ValidateAgentResponseTests(unittest.TestCase):
    def test_valid_payload_passes_validation_and_returns_typed_object(self):
        validated = validate_agent_response(VALID_BASE_PAYLOAD, BaseAgentResponse)

        self.assertIsInstance(validated, BaseAgentResponse)
        self.assertEqual(validated.metadata.agent_name, "sales")
        self.assertEqual(validated.metadata.report_run_id, "run-123")
        self.assertEqual(validated.warnings, [])

    def test_missing_required_field_fails_validation(self):
        payload = {"warnings": []}

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_agent_response(payload, BaseAgentResponse)

        error = ctx.exception
        self.assertEqual(error.schema_name, "BaseAgentResponse")
        self.assertTrue(any(item["field"] == "metadata" for item in error.field_errors))
        self.assertIn("metadata", str(error))

    def test_wrong_field_type_fails_validation(self):
        payload = {
            "metadata": {
                "agent_name": "sales",
                "report_run_id": "run-123",
            },
            "warnings": "not-a-list",
        }

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_agent_response(payload, BaseAgentResponse)

        error = ctx.exception
        self.assertTrue(any(item["field"] == "warnings" for item in error.field_errors))

    def test_invalid_enum_value_fails_validation(self):
        payload = {
            "status": "unknown",
            "metadata": {
                "agent_name": "sales",
            },
        }

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_agent_response(payload, DummyAgentResult)

        error = ctx.exception
        self.assertEqual(error.schema_name, "DummyAgentResult")
        self.assertTrue(any(item["field"] == "status" for item in error.field_errors))

    def test_extra_fields_are_forbidden(self):
        payload = {
            **VALID_BASE_PAYLOAD,
            "unexpected_field": "should-not-be-here",
        }

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_agent_response(payload, BaseAgentResponse)

        error = ctx.exception
        self.assertTrue(
            any(
                item["field"] == "unexpected_field" or "extra" in item["type"]
                for item in error.field_errors
            )
        )

    def test_error_message_contains_field_level_details(self):
        payload = {
            "metadata": {
                "agent_name": 123,
            },
        }

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_agent_response(payload, BaseAgentResponse)

        message = str(ctx.exception)
        self.assertIn("metadata", message)
        self.assertIn("BaseAgentResponse", message)

    def test_error_message_does_not_include_raw_full_payload(self):
        sensitive_value = "customer-secret-value-that-must-not-leak"
        payload = {
            "metadata": {
                "agent_name": sensitive_value,
                "report_run_id": "run-123",
            },
            "warnings": [
                {
                    "code": "w1",
                    "message": 42,
                }
            ],
        }

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_agent_response(payload, BaseAgentResponse)

        message = str(ctx.exception)
        self.assertNotIn(sensitive_value, message)

    def test_non_dict_payload_fails_validation_without_raw_payload_in_message(self):
        payload = ["not", "a", "dict"]

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_agent_response(payload, BaseAgentResponse)

        message = str(ctx.exception)
        self.assertIn("JSON object", message)
        self.assertNotIn("not", message)

    def test_dummy_future_agent_schema_can_use_validator(self):
        payload = {
            "status": "ok",
            "metadata": {
                "agent_name": "content",
                "report_run_id": "run-456",
            },
            "summary": "Three drafts ready.",
        }

        validated = validate_agent_response(payload, DummyAgentResult)

        self.assertEqual(validated.status, DummyStatus.OK)
        self.assertEqual(validated.metadata.agent_name, "content")
        self.assertEqual(validated.summary, "Three drafts ready.")


class ExportJsonSchemaTests(unittest.TestCase):
    def test_export_json_schema_returns_dictionary(self):
        schema = export_json_schema(BaseAgentResponse)

        self.assertIsInstance(schema, dict)
        self.assertEqual(schema.get("title"), "BaseAgentResponse")
        self.assertIn("properties", schema)
        self.assertIn("metadata", schema["properties"])
        self.assertIn("warnings", schema["properties"])

    def test_export_json_schema_rejects_invalid_model(self):
        with self.assertRaises(AgentSchemaConfigurationError):
            export_json_schema(dict)  # type: ignore[arg-type]


class AgentWarningModelTests(unittest.TestCase):
    def test_warnings_default_to_empty_list(self):
        validated = validate_agent_response(
            {
                "metadata": {
                    "agent_name": "support",
                },
            },
            BaseAgentResponse,
        )

        self.assertEqual(validated.warnings, [])

    def test_nested_warning_model_validates(self):
        payload = {
            "metadata": {
                "agent_name": "support",
            },
            "warnings": [
                {
                    "code": "partial_data",
                    "message": "Some threads were skipped.",
                }
            ],
        }

        validated = validate_agent_response(payload, BaseAgentResponse)

        self.assertEqual(len(validated.warnings), 1)
        self.assertIsInstance(validated.warnings[0], AgentWarning)
        self.assertEqual(validated.warnings[0].code, "partial_data")


class StrictAgentModelTests(unittest.TestCase):
    def test_strict_agent_model_forbids_extra_fields(self):
        class ExampleModel(StrictAgentModel):
            name: str = Field(default="example")

        with self.assertRaises(AgentSchemaValidationError):
            validate_agent_response({"name": "ok", "extra": True}, ExampleModel)
