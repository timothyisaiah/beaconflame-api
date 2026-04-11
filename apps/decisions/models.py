import uuid

from django.db import models

from apps.applications.models import Application
from apps.authentication.models import User


class DecisionType(models.TextChoices):
    APPROVED = "approved", "Approved"
    MANUAL_REVIEW = "manual_review", "Manual review"
    DECLINED = "declined", "Declined"


class DecisionSource(models.TextChoices):
    PIPELINE = "pipeline", "Pipeline"
    OVERRIDE = "override", "Override"


class Decision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="decisions")
    decision_type = models.CharField(max_length=32, choices=DecisionType.choices)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    risk_band = models.CharField(max_length=32, blank=True, default="")
    reason_summary = models.TextField(blank=True, default="")
    source = models.CharField(max_length=32, choices=DecisionSource.choices, default=DecisionSource.PIPELINE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=True, db_index=True)
    overridden_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decision_overrides",
    )
    override_reason = models.TextField(blank=True, default="")
    previous_decision = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseding_decisions",
    )

    class Meta:
        db_table = "decision"
        ordering = ["-created_at"]
