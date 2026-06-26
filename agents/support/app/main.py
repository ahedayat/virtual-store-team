"""Support-agent FastAPI application."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException

from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.support import SupportRunResponse
from agents.support.analysis import run_support_analysis
from agents.support.app.schemas import SupportRunRequest
from agents.support.validation import SupportLLMOutputError

SERVICE_NAME = "support-agent"

logger = logging.getLogger(__name__)

app = FastAPI(title=SERVICE_NAME)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": SERVICE_NAME, "message": "placeholder"}


def _validation_error_detail(
    exc: AgentSchemaValidationError | SupportLLMOutputError,
) -> dict[str, object]:
    if isinstance(exc, AgentSchemaValidationError):
        return {
            "code": "schema_validation_failed",
            "message": str(exc),
            "schema_name": exc.schema_name,
            "field_errors": exc.field_errors,
        }

    return {
        "code": "llm_output_invalid",
        "message": str(exc),
    }


@app.post("/run", response_model=SupportRunResponse)
def run_support_agent(
    payload: SupportRunRequest,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> SupportRunResponse:
    """Run the Support Agent scaffold pipeline and return structured mock output."""
    request_id = x_request_id or payload.request_id

    logger.info(
        "Support analysis run requested",
        extra={
            "service": SERVICE_NAME,
            "channel": payload.channel,
            "request_id": request_id,
        },
    )

    try:
        return run_support_analysis(
            customer_message=payload.customer_message,
            channel=payload.channel,
            tenant_id=payload.tenant_id,
            store_id=payload.store_id,
            metadata=payload.metadata,
            report_run_id=payload.report_run_id,
            output_language=payload.output_language,
            request_id=request_id,
        )
    except (AgentSchemaValidationError, SupportLLMOutputError) as exc:
        raise HTTPException(status_code=422, detail=_validation_error_detail(exc)) from None
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=501,
            detail={
                "code": "not_implemented",
                "message": str(exc),
            },
        ) from None
