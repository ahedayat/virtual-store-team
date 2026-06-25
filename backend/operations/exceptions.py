class ActionServiceError(Exception):
    """Base error for action service failures."""


class ActionPayloadValidationError(ActionServiceError):
    """Raised when an agent action payload fails validation."""


class ActionScopeError(ActionServiceError):
    """Raised when related records do not match trusted tenant/store scope."""


class ActionTransitionError(ActionServiceError):
    """Raised when an action lifecycle transition is invalid or unauthorized."""


class AgentOutputServiceError(Exception):
    """Base error for agent output service failures."""


class AgentOutputPayloadValidationError(AgentOutputServiceError):
    """Raised when an agent output payload fails validation."""


class AgentOutputScopeError(AgentOutputServiceError):
    """Raised when related records do not match trusted tenant/store scope."""
