import logging
from typing import Any

from django.db import transaction

from apps.audits.constants import EventType
from apps.audits.models import AuditLog

logger = logging.getLogger(__name__)

_VALID_EVENTS = {v for k, v in vars(EventType).items() if k.isupper()}


class AuditService:
    """Central audit entry point. Avoid storing raw PII in metadata."""

    @staticmethod
    @transaction.atomic
    def record(
        *,
        actor_type: str,
        actor_id: str | None,
        target_type: str,
        target_id: str,
        event_type: str,
        metadata: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        request_path: str | None = None,
    ) -> AuditLog:
        if event_type not in _VALID_EVENTS:
            logger.warning("Unknown audit event_type=%s", event_type)
        row = AuditLog.objects.create(
            actor_type=actor_type,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            event_type=event_type,
            metadata=metadata or {},
            correlation_id=correlation_id,
            request_path=request_path,
        )
        logger.info(
            "audit",
            extra={
                "audit_event": event_type,
                "target_type": target_type,
                "target_id": target_id,
                "correlation_id": correlation_id,
            },
        )
        return row
