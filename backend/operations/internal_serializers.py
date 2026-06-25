from rest_framework import serializers

from operations.constants import MAX_ACTION_PRIORITY, MIN_ACTION_PRIORITY, SUPPORTED_ACTION_TYPES
from operations.models import Action, AgentOutput


class InternalActionCreateRequestSerializer(serializers.Serializer):
    action_type = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    priority = serializers.IntegerField(
        min_value=MIN_ACTION_PRIORITY,
        max_value=MAX_ACTION_PRIORITY,
    )
    requires_approval = serializers.BooleanField(required=False, allow_null=True)
    low_risk = serializers.BooleanField(required=False)
    payload = serializers.JSONField(required=False, default=dict)
    report_run_id = serializers.UUIDField(required=False, allow_null=True)
    agent_output_id = serializers.UUIDField(required=False, allow_null=True)
    tenant_id = serializers.UUIDField(required=False, write_only=True)
    store_id = serializers.UUIDField(required=False, write_only=True)

    def validate_action_type(self, value):
        if value not in SUPPORTED_ACTION_TYPES:
            raise serializers.ValidationError(f"Unsupported action_type: {value!r}.")
        return value

    def validate_payload(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("payload must be a JSON object.")
        return value

    def build_service_payload(self) -> dict:
        data = self.validated_data
        payload = {
            "action_type": data["action_type"],
            "title": data["title"],
            "description": data["description"],
            "priority": data["priority"],
            "payload": data.get("payload", {}),
        }
        if "requires_approval" in data and data["requires_approval"] is not None:
            payload["requires_approval"] = data["requires_approval"]
        if "low_risk" in data:
            payload["low_risk"] = data["low_risk"]
        return payload


class InternalActionCreateResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = (
            "id",
            "action_type",
            "title",
            "priority",
            "requires_approval",
            "status",
            "agent_name",
            "report_run_id",
            "created_at",
        )


class InternalAgentOutputCreateRequestSerializer(serializers.Serializer):
    output_type = serializers.CharField(max_length=63)
    payload = serializers.JSONField()
    metadata = serializers.JSONField(required=False, default=dict)
    report_run_id = serializers.UUIDField(required=False, allow_null=True)
    tenant_id = serializers.UUIDField(required=False, write_only=True)
    store_id = serializers.UUIDField(required=False, write_only=True)

    def validate_output_type(self, value):
        if not value.strip():
            raise serializers.ValidationError("output_type is required and must be non-empty.")
        return value.strip()

    def validate_payload(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("payload must be a JSON object.")
        return value

    def validate_metadata(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be a JSON object.")
        return value


class InternalAgentOutputCreateResponseSerializer(serializers.ModelSerializer):
    output_type = serializers.SerializerMethodField()

    class Meta:
        model = AgentOutput
        fields = (
            "id",
            "agent_name",
            "output_type",
            "report_run_id",
            "created_at",
        )

    def get_output_type(self, obj: AgentOutput) -> str:
        return obj.output.get("output_type", "")


class InternalReportRunCompleteRequestSerializer(serializers.Serializer):
    report = serializers.JSONField()
    agent_output_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        default=list,
    )
    action_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        default=list,
    )
    metadata = serializers.JSONField(required=False, default=dict)
    tenant_id = serializers.UUIDField(required=False, write_only=True)
    store_id = serializers.UUIDField(required=False, write_only=True)

    def validate_report(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("report must be a JSON object.")
        if not value.get("generated_at"):
            raise serializers.ValidationError("report.generated_at is required.")
        return value

    def validate_metadata(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be a JSON object.")
        return value


class InternalReportRunCompleteResponseSerializer(serializers.Serializer):
    report_run_id = serializers.UUIDField()
    daily_report_id = serializers.UUIDField()
    status = serializers.CharField()
    completed_at = serializers.DateTimeField()
