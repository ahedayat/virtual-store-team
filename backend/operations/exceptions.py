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


class ReportRunServiceError(Exception):
    """Base error for report run service failures."""


class ReportRunPayloadValidationError(ReportRunServiceError):
    """Raised when a report completion payload fails validation."""


class ReportRunScopeError(ReportRunServiceError):
    """Raised when related records do not match trusted tenant/store scope."""


class ReportRunReferenceError(ReportRunServiceError):
    """Raised when referenced agent outputs or actions are invalid."""


class ReportRunTransitionError(ReportRunServiceError):
    """Raised when a report run lifecycle transition is invalid."""


class ReportRunPermissionError(ReportRunServiceError):
    """Raised when a service is not allowed to complete report runs."""
