"""Validation utilities for agent JSON response payloads."""

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from agents.shared.schemas.errors import (
    AgentSchemaConfigurationError,
    AgentSchemaValidationError,
)

T = TypeVar("T", bound=BaseModel)


def _ensure_schema_model(schema_model: type[BaseModel]) -> None:
    if not isinstance(schema_model, type) or not issubclass(schema_model, BaseModel):
        raise AgentSchemaConfigurationError(
            "schema_model must be a Pydantic BaseModel subclass."
        )


def _format_field_path(location: tuple[object, ...]) -> str:
    parts: list[str] = []
    for item in location:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            if parts and not parts[-1].startswith("["):
                parts.append(".")
            parts.append(str(item))
    return "".join(parts)


def _build_field_errors(exc: ValidationError) -> list[dict[str, str]]:
    field_errors: list[dict[str, str]] = []
    for error in exc.errors():
        field_errors.append(
            {
                "field": _format_field_path(error.get("loc", ())),
                "message": str(error.get("msg", "validation error")),
                "type": str(error.get("type", "value_error")),
            }
        )
    return field_errors


def _build_validation_message(
    schema_name: str,
    field_errors: list[dict[str, str]],
) -> str:
    if not field_errors:
        return f"Agent response failed validation against schema '{schema_name}'."

    details = "; ".join(
        f"{item['field']}: {item['message']}" for item in field_errors
    )
    return (
        f"Agent response failed validation against schema '{schema_name}': "
        f"{details}"
    )


def validate_agent_response(payload: dict, schema_model: type[T]) -> T:
    """Validate a parsed JSON payload against a Pydantic schema model."""
    _ensure_schema_model(schema_model)

    if not isinstance(payload, dict):
        schema_name = schema_model.__name__
        raise AgentSchemaValidationError(
            (
                f"Agent response failed validation against schema '{schema_name}': "
                "payload must be a JSON object."
            ),
            schema_name=schema_name,
            field_errors=[
                {
                    "field": "<root>",
                    "message": "payload must be a JSON object",
                    "type": "type_error",
                }
            ],
        )

    try:
        return schema_model.model_validate(payload)
    except ValidationError as exc:
        field_errors = _build_field_errors(exc)
        schema_name = schema_model.__name__
        raise AgentSchemaValidationError(
            _build_validation_message(schema_name, field_errors),
            schema_name=schema_name,
            field_errors=field_errors,
        ) from None


def export_json_schema(schema_model: type[BaseModel]) -> dict:
    """Export a JSON Schema document for a Pydantic schema model."""
    _ensure_schema_model(schema_model)
    return schema_model.model_json_schema()
