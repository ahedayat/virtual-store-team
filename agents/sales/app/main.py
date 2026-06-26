"""Sales-agent FastAPI application."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException

from agents.sales.analysis import run_sales_analysis
from agents.sales.app.schemas import SalesRunRequest
from agents.sales.validation import SalesLLMOutputError
from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.sales import SalesAnalysisResult

SERVICE_NAME = "sales-agent"

logger = logging.getLogger(__name__)

app = FastAPI(title=SERVICE_NAME)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": SERVICE_NAME, "message": "placeholder"}


def _validation_error_detail(
    exc: AgentSchemaValidationError | SalesLLMOutputError,
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


@app.post("/run", response_model=SalesAnalysisResult)
def run_sales_agent(
    payload: SalesRunRequest,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> SalesAnalysisResult:
    """Run the Sales Agent pipeline and return only schema-validated output."""
    request_id = x_request_id or payload.request_id

    logger.info(
        "Sales analysis run requested",
        extra={
            "service": SERVICE_NAME,
            "report_run_id": payload.report_run_id,
            "request_id": request_id,
        },
    )

    try:
        return run_sales_analysis(
            context=payload.context,
            sales_summary=payload.sales_summary,
            report_run_id=payload.report_run_id,
            output_language=payload.output_language,
            request_id=request_id,
        )
    except (AgentSchemaValidationError, SalesLLMOutputError) as exc:
        raise HTTPException(status_code=422, detail=_validation_error_detail(exc)) from None
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=501,
            detail={
                "code": "not_implemented",
                "message": str(exc),
            },
        ) from None
