import uuid

from django.db import models

from apps.applications.models import Application


class ScoreResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name="score_result",
    )
    score = models.DecimalField(max_digits=6, decimal_places=2)
    risk_band = models.CharField(max_length=32)
    components = models.JSONField(default=dict)
    engine_version = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "score_result"
