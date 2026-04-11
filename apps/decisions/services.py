from decimal import Decimal

from django.db import transaction

from apps.applications.models import Application, ApplicationStatus
from apps.audits.constants import ActorType, EventType
from apps.audits.services import AuditService
from apps.authentication.models import User
from apps.decisions.models import Decision, DecisionSource, DecisionType


class DecisionService:
    @staticmethod
    @transaction.atomic
    def create_pipeline_decision(
        *,
        application: Application,
        decision_type: str,
        score: Decimal | None,
        risk_band: str,
        reason_summary: str,
        correlation_id: str | None,
        actor_type: str = ActorType.SYSTEM,
        actor_id: str | None = None,
    ) -> Decision:
        Decision.objects.filter(application=application, is_current=True).update(is_current=False)
        d = Decision.objects.create(
            application=application,
            decision_type=decision_type,
            score=score,
            risk_band=risk_band or "",
            reason_summary=reason_summary,
            source=DecisionSource.PIPELINE,
            is_current=True,
        )
        status_map = {
            DecisionType.APPROVED: ApplicationStatus.APPROVED,
            DecisionType.DECLINED: ApplicationStatus.DECLINED,
            DecisionType.MANUAL_REVIEW: ApplicationStatus.MANUAL_REVIEW,
        }
        application.status = status_map.get(decision_type, ApplicationStatus.MANUAL_REVIEW)
        application.save(update_fields=["status", "updated_at"])
        AuditService.record(
            actor_type=actor_type,
            actor_id=actor_id,
            target_type="application",
            target_id=str(application.id),
            event_type=EventType.DECISION_CREATED,
            correlation_id=correlation_id,
            metadata={
                "decision_id": str(d.id),
                "decision_type": decision_type,
                "source": DecisionSource.PIPELINE,
            },
        )
        AuditService.record(
            actor_type=actor_type,
            actor_id=actor_id,
            target_type="application",
            target_id=str(application.id),
            event_type=EventType.APPLICATION_STATUS_CHANGED,
            correlation_id=correlation_id,
            metadata={"status": application.status},
        )
        return d

    @staticmethod
    @transaction.atomic
    def override_decision(
        *,
        application: Application,
        user: User,
        new_decision_type: str,
        reason: str,
        correlation_id: str | None,
    ) -> Decision:
        current = Decision.objects.filter(application=application, is_current=True).first()
        Decision.objects.filter(application=application, is_current=True).update(is_current=False)
        d = Decision.objects.create(
            application=application,
            decision_type=new_decision_type,
            score=current.score if current else None,
            risk_band=current.risk_band if current else "",
            reason_summary=f"Override: {reason}",
            source=DecisionSource.OVERRIDE,
            is_current=True,
            overridden_by=user,
            override_reason=reason,
            previous_decision=current,
        )
        status_map = {
            DecisionType.APPROVED: ApplicationStatus.APPROVED,
            DecisionType.DECLINED: ApplicationStatus.DECLINED,
            DecisionType.MANUAL_REVIEW: ApplicationStatus.MANUAL_REVIEW,
        }
        application.status = status_map.get(new_decision_type, ApplicationStatus.MANUAL_REVIEW)
        application.save(update_fields=["status", "updated_at"])
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=str(user.id),
            target_type="application",
            target_id=str(application.id),
            event_type=EventType.DECISION_OVERRIDDEN,
            correlation_id=correlation_id,
            metadata={
                "decision_id": str(d.id),
                "new_decision_type": new_decision_type,
                "previous_decision_id": str(current.id) if current else None,
            },
        )
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=str(user.id),
            target_type="application",
            target_id=str(application.id),
            event_type=EventType.APPLICATION_STATUS_CHANGED,
            correlation_id=correlation_id,
            metadata={"status": application.status},
        )
        return d
