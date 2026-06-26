"""Exceptions raised by shared agent response schema validation."""


class AgentSchemaError(Exception):
    """Base exception for agent schema validation failures."""


class AgentSchemaConfigurationError(AgentSchemaError):
    """Raised when a schema model is misconfigured or not a valid Pydantic model."""


class AgentSchemaValidationError(AgentSchemaError):
    """Raised when an agent response payload fails schema validation."""

    def __init__(
        self,
        message: str,
        *,
        schema_name: str,
        field_errors: list[dict[str, str]] | None = None,
    ) -> None:
        self.schema_name = schema_name
        self.field_errors = field_errors or []
        super().__init__(message)
