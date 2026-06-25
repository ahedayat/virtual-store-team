from rest_framework.exceptions import NotFound

from operations.models import AgentOutput, ReportRun
from stores.models import Store
from tenants.models import Tenant


def resolve_tenant_and_store(request) -> tuple[Tenant, Store]:
    identity = request.ai_service

    try:
        tenant = Tenant.objects.get(pk=identity.tenant_id)
    except Tenant.DoesNotExist as exc:
        raise NotFound("Store not found.") from exc

    try:
        store = Store.objects.get_for_tenant(tenant, pk=identity.store_id)
    except Store.DoesNotExist as exc:
        raise NotFound("Store not found.") from exc

    return tenant, store


def resolve_report_run(
    *,
    tenant: Tenant,
    store: Store,
    report_run_id,
) -> ReportRun | None:
    if report_run_id is None:
        return None

    try:
        return ReportRun.objects.get(
            pk=report_run_id,
            tenant=tenant,
            store=store,
        )
    except ReportRun.DoesNotExist as exc:
        raise NotFound("Report run not found.") from exc


def resolve_agent_output(
    *,
    tenant: Tenant,
    store: Store,
    agent_output_id,
) -> AgentOutput | None:
    if agent_output_id is None:
        return None

    try:
        return AgentOutput.objects.get(
            pk=agent_output_id,
            tenant=tenant,
            store=store,
        )
    except AgentOutput.DoesNotExist as exc:
        raise NotFound("Agent output not found.") from exc
