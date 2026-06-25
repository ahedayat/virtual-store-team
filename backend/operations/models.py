import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from stores.models import Store
from tenants.models import Tenant, TenantScopedModel

from operations.constants import (
    ACTION_EVENT_ACTOR_AGENT,
    ACTION_EVENT_ACTOR_SYSTEM,
    ACTION_EVENT_ACTOR_USER,
    ACTION_EVENT_TYPE_APPROVED,
    ACTION_EVENT_TYPE_CREATED,
    ACTION_EVENT_TYPE_QUEUED,
    ACTION_EVENT_TYPE_REJECTED,
    ACTION_STATUS_APPROVED,
    ACTION_STATUS_CANCELLED,
    ACTION_STATUS_EXECUTED,
    ACTION_STATUS_EXECUTING,
    ACTION_STATUS_FAILED,
    ACTION_STATUS_PENDING_APPROVAL,
    ACTION_STATUS_QUEUED,
    ACTION_STATUS_REJECTED,
    REPORT_RUN_STATUS_COMPLETED,
    REPORT_RUN_STATUS_FAILED,
    REPORT_RUN_STATUS_QUEUED,
    REPORT_RUN_STATUS_RUNNING,
)


class ReportRunStatus(models.TextChoices):
    QUEUED = REPORT_RUN_STATUS_QUEUED, "Queued"
    RUNNING = REPORT_RUN_STATUS_RUNNING, "Running"
    COMPLETED = REPORT_RUN_STATUS_COMPLETED, "Completed"
    FAILED = REPORT_RUN_STATUS_FAILED, "Failed"


class ActionStatus(models.TextChoices):
    PENDING_APPROVAL = ACTION_STATUS_PENDING_APPROVAL, "Pending approval"
    QUEUED = ACTION_STATUS_QUEUED, "Queued"
    APPROVED = ACTION_STATUS_APPROVED, "Approved"
    REJECTED = ACTION_STATUS_REJECTED, "Rejected"
    CANCELLED = ACTION_STATUS_CANCELLED, "Cancelled"
    EXECUTING = ACTION_STATUS_EXECUTING, "Executing"
    EXECUTED = ACTION_STATUS_EXECUTED, "Executed"
    FAILED = ACTION_STATUS_FAILED, "Failed"


class ActionEventType(models.TextChoices):
    CREATED = ACTION_EVENT_TYPE_CREATED, "Created"
    APPROVED = ACTION_EVENT_TYPE_APPROVED, "Approved"
    REJECTED = ACTION_EVENT_TYPE_REJECTED, "Rejected"
    QUEUED = ACTION_EVENT_TYPE_QUEUED, "Queued"


class ActionEventActorType(models.TextChoices):
    AGENT = ACTION_EVENT_ACTOR_AGENT, "Agent"
    SYSTEM = ACTION_EVENT_ACTOR_SYSTEM, "System"
    USER = ACTION_EVENT_ACTOR_USER, "User"


class ReportRun(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="report_runs",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="report_runs",
    )
    status = models.CharField(
        max_length=32,
        choices=ReportRunStatus.choices,
        default=ReportRunStatus.QUEUED,
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})

    def __str__(self):
        return f"ReportRun {self.id} ({self.status})"


class DailyReport(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="daily_reports",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="daily_reports",
    )
    report_run = models.OneToOneField(
        ReportRun,
        on_delete=models.CASCADE,
        related_name="daily_report",
    )
    content = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-generated_at"]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})
        if (
            self.report_run_id
            and self.tenant_id
            and self.report_run.tenant_id != self.tenant_id
        ):
            raise ValidationError({"report_run": "Report run must belong to the same tenant."})
        if self.report_run_id and self.store_id and self.report_run.store_id != self.store_id:
            raise ValidationError({"report_run": "Report run must belong to the same store."})

    def __str__(self):
        return f"DailyReport {self.id}"


class AgentOutput(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="agent_outputs",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="agent_outputs",
    )
    report_run = models.ForeignKey(
        ReportRun,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agent_outputs",
    )
    agent_name = models.CharField(max_length=63)
    output = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})
        if (
            self.report_run_id
            and self.tenant_id
            and self.report_run.tenant_id != self.tenant_id
        ):
            raise ValidationError({"report_run": "Report run must belong to the same tenant."})
        if self.report_run_id and self.store_id and self.report_run.store_id != self.store_id:
            raise ValidationError({"report_run": "Report run must belong to the same store."})

    def __str__(self):
        return f"AgentOutput {self.id} ({self.agent_name})"


class Action(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="actions",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="actions",
    )
    report_run = models.ForeignKey(
        ReportRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )
    source_agent_output = models.ForeignKey(
        AgentOutput,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )
    agent_name = models.CharField(max_length=63)
    action_type = models.CharField(max_length=63)
    title = models.CharField(max_length=255)
    description = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    priority = models.PositiveSmallIntegerField()
    requires_approval = models.BooleanField()
    status = models.CharField(max_length=32, choices=ActionStatus.choices)
    status_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_actions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    execution_result = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["priority", "-created_at"]

    def clean(self):
        super().clean()
        if self.store_id and self.tenant_id and self.store.tenant_id != self.tenant_id:
            raise ValidationError({"store": "Store must belong to the same tenant."})
        if (
            self.report_run_id
            and self.tenant_id
            and self.report_run.tenant_id != self.tenant_id
        ):
            raise ValidationError({"report_run": "Report run must belong to the same tenant."})
        if self.report_run_id and self.store_id and self.report_run.store_id != self.store_id:
            raise ValidationError({"report_run": "Report run must belong to the same store."})
        if (
            self.source_agent_output_id
            and self.tenant_id
            and self.source_agent_output.tenant_id != self.tenant_id
        ):
            raise ValidationError(
                {"source_agent_output": "Agent output must belong to the same tenant."}
            )
        if (
            self.source_agent_output_id
            and self.store_id
            and self.source_agent_output.store_id != self.store_id
        ):
            raise ValidationError(
                {"source_agent_output": "Agent output must belong to the same store."}
            )

    def __str__(self):
        return f"{self.action_type}: {self.title}"


class ActionEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.ForeignKey(
        Action,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=32, choices=ActionEventType.choices)
    previous_status = models.CharField(
        max_length=32,
        choices=ActionStatus.choices,
        blank=True,
    )
    new_status = models.CharField(max_length=32, choices=ActionStatus.choices)
    reason = models.TextField(blank=True)
    actor_type = models.CharField(max_length=16, choices=ActionEventActorType.choices)
    actor_id = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.event_type} → {self.new_status} ({self.action_id})"
