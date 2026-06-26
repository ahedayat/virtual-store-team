from rest_framework import serializers

from operations.dashboard_service import DashboardPaginationDefaults
from operations.history_constants import DEFAULT_HISTORY_LIMIT, MAX_HISTORY_LIMIT


class ISODateTimeField(serializers.DateTimeField):
    """Accept ISO 8601 datetimes including trailing Z (UTC)."""

    def to_internal_value(self, value):
        if isinstance(value, str) and value.endswith("Z"):
            value = f"{value[:-1]}+00:00"
        return super().to_internal_value(value)


class HistoryFeedQuerySerializer(serializers.Serializer):
    type = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    agent_name = serializers.CharField(required=False)
    report_run_id = serializers.UUIDField(required=False)
    action_id = serializers.UUIDField(required=False)
    from_timestamp = ISODateTimeField(required=False)
    to_timestamp = ISODateTimeField(required=False)
    limit = serializers.IntegerField(
        required=False,
        default=DEFAULT_HISTORY_LIMIT,
        min_value=1,
        max_value=MAX_HISTORY_LIMIT,
    )
    offset = serializers.IntegerField(required=False, default=0, min_value=0)

    def validate(self, attrs):
        from_timestamp = attrs.get("from_timestamp")
        to_timestamp = attrs.get("to_timestamp")
        if from_timestamp and to_timestamp and from_timestamp > to_timestamp:
            raise serializers.ValidationError(
                {"from": "from must be earlier than or equal to to."}
            )
        return attrs


class DashboardPaginationQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(
        required=False,
        default=DashboardPaginationDefaults.DEFAULT_LIMIT,
        min_value=1,
        max_value=DashboardPaginationDefaults.MAX_LIMIT,
    )
    offset = serializers.IntegerField(required=False, default=0, min_value=0)


class ActionListQuerySerializer(DashboardPaginationQuerySerializer):
    status = serializers.CharField(required=False)
    action_type = serializers.CharField(required=False)
    agent_name = serializers.CharField(required=False)
    requires_approval = serializers.BooleanField(required=False)
    from_timestamp = ISODateTimeField(required=False)
    to_timestamp = ISODateTimeField(required=False)

    def validate(self, attrs):
        from_timestamp = attrs.get("from_timestamp")
        to_timestamp = attrs.get("to_timestamp")
        if from_timestamp and to_timestamp and from_timestamp > to_timestamp:
            raise serializers.ValidationError(
                {"from": "from must be earlier than or equal to to."}
            )
        return attrs


class ActionApproveRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class ActionRejectRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)
