"""Sales-agent FastAPI application."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Header, HTTPException

from agents.sales.action_mapping import (
    SalesActionMappingError,
    map_sales_analysis_to_actions,
    persist_sales_actions,
)
from agents.sales.analysis import run_sales_analysis
from agents.sales.app.schemas import SalesRunRequest
from agents.sales.validation import SalesLLMOutputError
from agents.shared.django_client import DjangoClient
from agents.shared.django_client.errors import DjangoClientError, DjangoHTTPError
from agents.shared.schemas.base import AgentWarning
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


def _build_django_client(
    *,
    service_token: str | None,
    request_id: str | None,
) -> DjangoClient | None:
    token = service_token or os.environ.get("JWT_SERVICE_TOKEN")
    if not token:
        return None
    return DjangoClient(service_token=token, request_id=request_id)


def _append_warning(result: SalesAnalysisResult, warning: AgentWarning) -> SalesAnalysisResult:
    return result.model_copy(update={"warnings": list(result.warnings) + [warning]})


@app.post("/run", response_model=SalesAnalysisResult)
def run_sales_agent(
    payload: SalesRunRequest,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> SalesAnalysisResult:
    """Run the Sales Agent pipeline and return only schema-validated output."""
    request_id = x_request_id or payload.request_id

    logger.info(
        "Sales analysis run requested",
        extra={
            "service": SERVICE_NAME,
            "report_run_id": payload.report_run_id,
            "request_id": request_id,
            "fetch_from_django": payload.fetch_from_django,
            "persist_actions": payload.persist_actions,
            "dry_run": payload.dry_run,
        },
    )

    service_token = payload.service_token
    if service_token is None and authorization and authorization.startswith("Bearer "):
        service_token = authorization.removeprefix("Bearer ").strip()

    django_client = None
    if payload.fetch_from_django or payload.persist_actions:
        django_client = _build_django_client(
            service_token=service_token,
            request_id=request_id,
        )

    try:
        result = run_sales_analysis(
            context=payload.context,
            sales_summary=payload.sales_summary,
            inventory=payload.inventory,
            store_id=payload.store_id,
            report_run_id=payload.report_run_id,
            output_language=payload.output_language,
            request_id=request_id,
            django_client=django_client,
            fetch_from_django=payload.fetch_from_django,
        )

        if payload.persist_actions:
            if django_client is None:
                result = _append_warning(
                    result,
                    AgentWarning(
                        code="action_persistence_skipped",
                        message=(
                            "Action persistence requested but no Django client "
                            "could be configured."
                        ),
                    ),
                )
            else:
                try:
                    mapped_or_persisted = persist_sales_actions(
                        result,
                        django_client=django_client,
                        report_run_id=payload.report_run_id,
                        dry_run=payload.dry_run,
                    )
                    if payload.dry_run:
                        result = _append_warning(
                            result,
                            AgentWarning(
                                code="dry_run",
                                message=(
                                    f"{len(mapped_or_persisted)} sales action(s) mapped "
                                    "but not persisted."
                                ),
                            ),
                        )
                except SalesActionMappingError as exc:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "code": "action_mapping_failed",
                            "message": str(exc),
                        },
                    ) from None
                except DjangoHTTPError as exc:
                    result = _append_warning(
                        result,
                        AgentWarning(
                            code="action_persistence_failed",
                            message=str(exc),
                        ),
                    )
                except DjangoClientError as exc:
                    result = _append_warning(
                        result,
                        AgentWarning(
                            code="action_persistence_failed",
                            message=str(exc),
                        ),
                    )

        return result
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
