"""Content-agent FastAPI application."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException

from agents.content.analysis import run_content_analysis
from agents.content.app.schemas import ContentRunRequest
from agents.content.validation import ContentLLMOutputError
from agents.shared.schemas.content import ContentSuggestions
from agents.shared.schemas.errors import AgentSchemaValidationError

SERVICE_NAME = "content-agent"

logger = logging.getLogger(__name__)

app = FastAPI(title=SERVICE_NAME)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": SERVICE_NAME, "message": "placeholder"}


def _validation_error_detail(
    exc: AgentSchemaValidationError | ContentLLMOutputError,
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


@app.post("/run", response_model=ContentSuggestions)
def run_content_agent(
    payload: ContentRunRequest,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> ContentSuggestions:
    """Run the Content Agent pipeline and return only schema-validated output."""
    request_id = x_request_id or payload.request_id

    logger.info(
        "Content analysis run requested",
        extra={
            "service": SERVICE_NAME,
            "report_run_id": payload.report_run_id,
            "request_id": request_id,
        },
    )

    try:
        return run_content_analysis(
            context=payload.context,
            products=payload.products,
            store_context=payload.store_context,
            campaign_angle=payload.campaign_angle,
            report_run_id=payload.report_run_id,
            output_language=payload.output_language,
            max_drafts_per_run=payload.max_drafts_per_run,
            request_id=request_id,
        )
    except (AgentSchemaValidationError, ContentLLMOutputError) as exc:
        raise HTTPException(status_code=422, detail=_validation_error_detail(exc)) from None
