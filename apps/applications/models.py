import uuid

from django.db import models

from apps.authentication.models import User, APIKey


class ApplicationStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    PROCESSING = "processing", "Processing"
    MANUAL_REVIEW = "manual_review", "Manual review"
    APPROVED = "approved", "Approved"
    DECLINED = "declined", "Declined"
    FAILED = "failed", "Failed"


class PrincipalKind(models.TextChoices):
    USER = "user", "User"
    API_KEY = "api_key", "API key"


class Application(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_reference = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(
        max_length=32,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.QUEUED,
        db_index=True,
    )
    raw_payload = models.JSONField()
    correlation_id = models.CharField(max_length=64, blank=True, default="")
    idempotency_key = models.CharField(max_length=128, null=True, blank=True)
    principal_kind = models.CharField(max_length=16, choices=PrincipalKind.choices)
    principal_id = models.CharField(max_length=64)
    submitted_by_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications_submitted",
    )
    submitted_by_api_key = models.ForeignKey(
        APIKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications_submitted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "application"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key", "principal_kind", "principal_id"],
                name="uniq_application_idempotency_principal",
                condition=models.Q(idempotency_key__isnull=False),
            ),
        ]


class FeatureSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name="feature_snapshot",
    )
    data = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feature_snapshot"
