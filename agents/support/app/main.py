"""Support-agent FastAPI application."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Header, HTTPException

from agents.shared.django_client import DjangoClient
from agents.shared.django_client.errors import DjangoClientError, DjangoHTTPError
from agents.shared.schemas.base import AgentWarning
from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.support import SupportInsights, SupportRunResponse
from agents.support.action_mapping import (
    SupportActionMappingError,
    persist_support_actions,
)
from agents.support.analysis import run_support_analysis
from agents.support.app.schemas import SupportRunRequest
from agents.support.validation import (
    SupportLLMOutputError,
    support_insights_to_run_response,
)

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


def _build_django_client(
    *,
    service_token: str | None,
    request_id: str | None,
) -> DjangoClient | None:
    token = service_token or os.environ.get("JWT_SERVICE_TOKEN")
    if not token:
        return None
    return DjangoClient(service_token=token, request_id=request_id)


def _append_warning(result: SupportInsights, warning: AgentWarning) -> SupportInsights:
    return result.model_copy(update={"warnings": list(result.warnings) + [warning]})


@app.post("/run", response_model=SupportRunResponse)
def run_support_agent(
    payload: SupportRunRequest,
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> SupportRunResponse:
    """Run the Support Agent runtime pipeline and return structured output."""
    request_id = x_request_id or payload.request_id

    logger.info(
        "Support analysis run requested",
        extra={
            "service": SERVICE_NAME,
            "channel": payload.channel,
            "request_id": request_id,
            "fetch_recent_messages": payload.fetch_recent_messages,
            "persist_actions": payload.persist_actions,
            "dry_run": payload.dry_run,
        },
    )

    service_token = payload.service_token
    if service_token is None and authorization and authorization.startswith("Bearer "):
        service_token = authorization.removeprefix("Bearer ").strip()

    django_client = None
    if payload.fetch_recent_messages or payload.persist_actions:
        django_client = _build_django_client(
            service_token=service_token,
            request_id=request_id,
        )

    try:
        insights = run_support_analysis(
            customer_message=payload.customer_message,
            channel=payload.channel,
            tenant_id=payload.tenant_id,
            store_id=payload.store_id,
            metadata=payload.metadata,
            report_run_id=payload.report_run_id,
            output_language=payload.output_language,
            request_id=request_id,
            context=payload.context,
            message_threads=payload.message_threads,
            django_client=django_client,
            fetch_recent_messages=payload.fetch_recent_messages,
        )

        if payload.persist_actions:
            if django_client is None:
                insights = _append_warning(
                    insights,
                    AgentWarning(
                        code="support_action_persistence_skipped",
                        message=(
                            "Action persistence requested but no Django client "
                            "could be configured."
                        ),
                    ),
                )
            else:
                try:
                    mapped_or_persisted = persist_support_actions(
                        insights,
                        django_client=django_client,
                        report_run_id=payload.report_run_id,
                        dry_run=payload.dry_run,
                    )
                    if payload.dry_run:
                        insights = _append_warning(
                            insights,
                            AgentWarning(
                                code="dry_run",
                                message=(
                                    f"{len(mapped_or_persisted)} support action(s) mapped "
                                    "but not persisted."
                                ),
                            ),
                        )
                except SupportActionMappingError as exc:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "code": "support_action_mapping_failed",
                            "message": str(exc),
                        },
                    ) from None
                except DjangoHTTPError:
                    insights = _append_warning(
                        insights,
                        AgentWarning(
                            code="support_action_persistence_failed",
                            message="Support action persistence failed.",
                        ),
                    )
                except DjangoClientError:
                    insights = _append_warning(
                        insights,
                        AgentWarning(
                            code="support_action_persistence_failed",
                            message="Support action persistence failed.",
                        ),
                    )

        for warning in insights.warnings:
            logger.warning(
                "Support analysis warning",
                extra={
                    "service": SERVICE_NAME,
                    "warning_code": warning.code,
                    "request_id": request_id,
                },
            )
        return support_insights_to_run_response(
            insights,
            output_language=payload.output_language or "fa",
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
