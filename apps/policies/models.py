import uuid

from django.db import models


class PolicyOutcome(models.TextChoices):
    APPROVED = "approved", "Approved"
    MANUAL_REVIEW = "manual_review", "Manual review"
    DECLINED = "declined", "Declined"


class PolicyRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256)
    priority = models.IntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    condition = models.JSONField(default=dict)
    outcome = models.CharField(max_length=32, choices=PolicyOutcome.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "policy_rule"
        ordering = ["priority", "id"]
