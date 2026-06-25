from django.contrib import admin

from operations.models import (
    Action,
    ActionEvent,
    AgentOutput,
    DailyReport,
    ReportRun,
)


class ActionEventInline(admin.TabularInline):
    model = ActionEvent
    extra = 0
    readonly_fields = ("id", "created_at")
    fields = (
        "event_type",
        "previous_status",
        "new_status",
        "reason",
        "actor_type",
        "actor_id",
        "created_at",
    )


@admin.register(ReportRun)
class ReportRunAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "store", "status", "created_at", "updated_at")
    list_filter = ("tenant", "store", "status")
    search_fields = ("id", "tenant__name", "tenant__slug", "store__name", "store__slug")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "store", "report_run", "generated_at", "created_at")
    list_filter = ("tenant", "store")
    search_fields = ("id", "tenant__name", "store__name")
    ordering = ("-generated_at",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AgentOutput)
class AgentOutputAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "store", "agent_name", "report_run", "created_at")
    list_filter = ("tenant", "store", "agent_name")
    search_fields = ("id", "agent_name", "tenant__name", "store__name")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at")


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "action_type",
        "status",
        "priority",
        "requires_approval",
        "agent_name",
        "tenant",
        "store",
        "created_at",
    )
    list_filter = ("tenant", "store", "status", "action_type", "requires_approval", "agent_name")
    search_fields = ("title", "description", "action_type", "agent_name")
    ordering = ("priority", "-created_at")
    readonly_fields = ("id", "created_at", "updated_at", "decided_at", "executed_at")
    inlines = (ActionEventInline,)


@admin.register(ActionEvent)
class ActionEventAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "event_type",
        "previous_status",
        "new_status",
        "actor_type",
        "actor_id",
        "created_at",
    )
    list_filter = ("event_type", "new_status", "actor_type")
    search_fields = ("action__title", "reason", "actor_id")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at")
