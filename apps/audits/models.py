import uuid

from django.db import models

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_type = models.CharField(max_length=32)
    actor_id = models.CharField(max_length=64, null=True, blank=True)
    target_type = models.CharField(max_length=64)
    target_id = models.CharField(max_length=64)
    event_type = models.CharField(max_length=64, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    correlation_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    request_path = models.CharField(max_length=512, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["event_type", "timestamp"]),
        ]
