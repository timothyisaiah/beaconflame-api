import logging
from typing import Any

from django.db import IntegrityError, transaction

from apps.applications.models import Application, ApplicationStatus, PrincipalKind
from apps.audits.constants import ActorType, EventType
from apps.audits.services import AuditService
from apps.authentication.models import APIKey, User, UserRole

logger = logging.getLogger(__name__)


def _principal(request) -> tuple[str, str]:
    api_key = getattr(request, "api_key", None)
    if isinstance(api_key, APIKey):
        return PrincipalKind.API_KEY, str(api_key.id)
    user = request.user
    return PrincipalKind.USER, str(user.id)


def _audit_actor(request) -> tuple[str, str | None]:
    api_key = getattr(request, "api_key", None)
    if isinstance(api_key, APIKey):
        return ActorType.API_KEY, str(api_key.id)
    if request.user.is_authenticated:
        return ActorType.USER, str(request.user.id)
    return ActorType.SYSTEM, None


class ApplicationService:
    @staticmethod
    @transaction.atomic
    def submit(
        *,
        request,
        payload: dict[str, Any],
        external_reference: str,
        idempotency_key: str | None,
        correlation_id: str,
    ) -> tuple[Application, bool]:
        """
        Returns (application, created).
        Idempotent when idempotency_key is provided for the same principal.
        """
        principal_kind, principal_id = _principal(request)
        actor_type, actor_id = _audit_actor(request)

        if idempotency_key:
            existing = Application.objects.filter(
                idempotency_key=idempotency_key,
                principal_kind=principal_kind,
                principal_id=principal_id,
            ).first()
            if existing:
                logger.info(
                    "application_idempotent_hit",
                    extra={"application_id": str(existing.id), "correlation_id": correlation_id},
                )
                return existing, False

        submitted_by_user = request.user if principal_kind == PrincipalKind.USER else None
        submitted_by_api_key = getattr(request, "api_key", None) if principal_kind == PrincipalKind.API_KEY else None

        try:
            app = Application.objects.create(
                external_reference=external_reference or "",
                raw_payload=payload,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key or None,
                principal_kind=principal_kind,
                principal_id=principal_id,
                submitted_by_user=submitted_by_user,
                submitted_by_api_key=submitted_by_api_key,
                status=ApplicationStatus.QUEUED,
            )
        except IntegrityError:
            existing = Application.objects.filter(
                idempotency_key=idempotency_key,
                principal_kind=principal_kind,
                principal_id=principal_id,
            ).first()
            if existing:
                return existing, False
            raise

        AuditService.record(
            actor_type=actor_type,
            actor_id=actor_id,
            target_type="application",
            target_id=str(app.id),
            event_type=EventType.APPLICATION_SUBMITTED,
            correlation_id=correlation_id,
            metadata={
                "payload_keys": list(payload.keys()),
                "external_reference": external_reference,
            },
        )
        return app, True

    @staticmethod
    def visible_queryset_for_user(user: User, queryset):
        role = getattr(user, "role", None)
        if role in (UserRole.ADMIN, UserRole.ANALYST):
            return queryset
        return queryset.filter(principal_kind=PrincipalKind.USER, principal_id=str(user.id))

    @staticmethod
    def visible_queryset_for_request(request, queryset):
        user = request.user
        role = getattr(user, "role", None)
        if role in (UserRole.ADMIN, UserRole.ANALYST):
            return queryset
        api_key = getattr(request, "api_key", None)
        if isinstance(api_key, APIKey):
            return queryset.filter(
                principal_kind=PrincipalKind.API_KEY,
                principal_id=str(api_key.id),
            )
        return queryset.filter(principal_kind=PrincipalKind.USER, principal_id=str(user.id))
