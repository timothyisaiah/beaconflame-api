from rest_framework import serializers

from apps.applications.models import Application
from apps.authentication.models import APIKey, User, UserRole
from apps.authentication.api_keys import extract_prefix, hash_api_key
from apps.audits.models import AuditLog
from apps.decisions.models import Decision, DecisionType
from apps.policies.models import PolicyOutcome, PolicyRule


class ApplicationSubmitSerializer(serializers.Serializer):
    """Validated intake payload; arbitrary business fields live under payload."""

    external_reference = serializers.CharField(max_length=128, required=False, allow_blank=True)
    payload = serializers.JSONField()

    def validate_payload(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("payload must be an object.")
        if len(value) > 200:
            raise serializers.ValidationError("payload too large.")
        return value


class ApplicationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = (
            "id",
            "external_reference",
            "status",
            "correlation_id",
            "created_at",
            "updated_at",
        )


class ApplicationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = (
            "id",
            "external_reference",
            "status",
            "raw_payload",
            "correlation_id",
            "principal_kind",
            "created_at",
            "updated_at",
        )


class DecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Decision
        fields = (
            "id",
            "decision_type",
            "score",
            "risk_band",
            "reason_summary",
            "source",
            "created_at",
            "is_current",
            "override_reason",
            "overridden_by",
            "previous_decision",
        )
        read_only_fields = fields


class OverrideSerializer(serializers.Serializer):
    decision_type = serializers.ChoiceField(choices=DecisionType.choices)
    reason = serializers.CharField(min_length=3, max_length=4000)


class PolicyRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyRule
        fields = (
            "id",
            "name",
            "priority",
            "is_active",
            "condition",
            "outcome",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_outcome(self, value):
        valid = {c[0] for c in PolicyOutcome.choices}
        if value not in valid:
            raise serializers.ValidationError("Invalid outcome.")
        return value

    def validate_condition(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("condition must be an object.")
        return value


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = (
            "id",
            "actor_type",
            "actor_id",
            "target_type",
            "target_id",
            "event_type",
            "metadata",
            "correlation_id",
            "request_path",
            "timestamp",
        )


class APIKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=UserRole.API_CLIENT))


class APIKeyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = ("id", "name", "prefix", "created_at", "revoked_at", "user")
