import logging

from celery import shared_task
from django.db import OperationalError, transaction

from apps.applications.features import compute_feature_dict
from apps.applications.models import Application, ApplicationStatus, FeatureSnapshot
from apps.audits.constants import ActorType, EventType
from apps.audits.services import AuditService
from apps.decisions.services import DecisionService
from apps.integrations.models import WebhookDelivery, WebhookDeliveryStatus
from apps.policies.engine import RuleEngine, decimal_to_float
from apps.policies.models import PolicyRule
from apps.scoring.engine import WeightedScoringEngine
from apps.scoring.models import ScoreResult

logger = logging.getLogger(__name__)


def _fail(application_id: str, exc: Exception, stage: str, correlation_id: str | None):
    try:
        app = Application.objects.get(pk=application_id)
    except Application.DoesNotExist:
        return
    app.status = ApplicationStatus.FAILED
    app.save(update_fields=["status", "updated_at"])
    AuditService.record(
        actor_type=ActorType.SYSTEM,
        actor_id=None,
        target_type="application",
        target_id=str(application_id),
        event_type=EventType.PIPELINE_FAILED,
        correlation_id=correlation_id,
        metadata={"stage": stage, "error": str(exc)[:500]},
    )
    logger.exception(
        "pipeline_failed",
        extra={"application_id": application_id, "stage": stage, "correlation_id": correlation_id},
    )


@shared_task(
    bind=True,
    autoretry_for=(OperationalError, ConnectionError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def enrich_application(self, application_id: str):
    try:
        with transaction.atomic():
            app = Application.objects.select_for_update().get(pk=application_id)
            correlation_id = app.correlation_id or None
            app.status = ApplicationStatus.PROCESSING
            app.save(update_fields=["status", "updated_at"])
            AuditService.record(
                actor_type=ActorType.SYSTEM,
                actor_id=None,
                target_type="application",
                target_id=str(app.id),
                event_type=EventType.APPLICATION_STATUS_CHANGED,
                correlation_id=correlation_id,
                metadata={"status": app.status, "stage": "enrich"},
            )
            AuditService.record(
                actor_type=ActorType.SYSTEM,
                actor_id=None,
                target_type="application",
                target_id=str(app.id),
                event_type=EventType.ENRICHMENT_COMPLETED,
                correlation_id=correlation_id,
                metadata={"placeholder": True},
            )
    except Exception as exc:
        try:
            app = Application.objects.get(pk=application_id)
            cid = app.correlation_id
        except Application.DoesNotExist:
            cid = None
        _fail(application_id, exc, "enrich", cid)
        raise


@shared_task(
    bind=True,
    autoretry_for=(OperationalError, ConnectionError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def compute_features(self, application_id: str):
    try:
        app = Application.objects.get(pk=application_id)
        correlation_id = app.correlation_id or None
        data = compute_feature_dict(app.raw_payload or {})
        with transaction.atomic():
            snap, _ = FeatureSnapshot.objects.update_or_create(
                application=app,
                defaults={"data": data, "version": 1},
            )
        AuditService.record(
            actor_type=ActorType.SYSTEM,
            actor_id=None,
            target_type="application",
            target_id=str(app.id),
            event_type=EventType.FEATURES_COMPUTED,
            correlation_id=correlation_id,
            metadata={"snapshot_id": str(snap.id), "feature_keys": list(data.keys())},
        )
    except Exception as exc:
        try:
            app = Application.objects.get(pk=application_id)
            cid = app.correlation_id
        except Application.DoesNotExist:
            cid = None
        _fail(application_id, exc, "compute_features", cid)
        raise


@shared_task(
    bind=True,
    autoretry_for=(OperationalError, ConnectionError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def run_scoring(self, application_id: str):
    try:
        app = Application.objects.get(pk=application_id)
        correlation_id = app.correlation_id or None
        snap = app.feature_snapshot
        engine = WeightedScoringEngine()
        dto = engine.score(snap.data)
        with transaction.atomic():
            ScoreResult.objects.update_or_create(
                application=app,
                defaults={
                    "score": dto.score,
                    "risk_band": dto.risk_band,
                    "components": dto.components,
                    "engine_version": engine.version,
                },
            )
        AuditService.record(
            actor_type=ActorType.SYSTEM,
            actor_id=None,
            target_type="application",
            target_id=str(app.id),
            event_type=EventType.SCORE_GENERATED,
            correlation_id=correlation_id,
            metadata={
                "score": str(dto.score),
                "risk_band": dto.risk_band,
                "engine_version": engine.version,
            },
        )
    except Exception as exc:
        try:
            app = Application.objects.get(pk=application_id)
            cid = app.correlation_id
        except Application.DoesNotExist:
            cid = None
        _fail(application_id, exc, "run_scoring", cid)
        raise


@shared_task(
    bind=True,
    autoretry_for=(OperationalError, ConnectionError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def evaluate_rules(self, application_id: str):
    try:
        app = Application.objects.get(pk=application_id)
        correlation_id = app.correlation_id or None
        score_row = app.score_result
        rules = list(PolicyRule.objects.filter(is_active=True).order_by("priority", "id"))
        ctx = {
            "score": decimal_to_float(score_row.score),
            "risk_band": score_row.risk_band,
            "features": app.feature_snapshot.data,
        }
        result = RuleEngine().evaluate(rules, ctx)
        AuditService.record(
            actor_type=ActorType.SYSTEM,
            actor_id=None,
            target_type="application",
            target_id=str(app.id),
            event_type=EventType.RULES_EVALUATED,
            correlation_id=correlation_id,
            metadata={
                "matched_rule_id": result.matched_rule_id,
                "outcome": result.outcome,
                "evaluated": result.evaluated_rules,
            },
        )
        return {
            "application_id": application_id,
            "outcome": result.outcome,
            "matched_rule_id": result.matched_rule_id,
        }
    except Exception as exc:
        try:
            app = Application.objects.get(pk=application_id)
            cid = app.correlation_id
        except Application.DoesNotExist:
            cid = None
        _fail(application_id, exc, "evaluate_rules", cid)
        raise


@shared_task(
    bind=True,
    autoretry_for=(OperationalError, ConnectionError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def persist_decision(self, prev_result: dict | None, application_id: str | None = None):
    """
    Celery chain may pass previous task return as first arg when using link order.
    We accept (application_id) only via immutable signatures from the chain builder.
    """
    app_id = application_id
    outcome = None
    if isinstance(prev_result, dict) and "application_id" in prev_result:
        app_id = prev_result["application_id"]
        outcome = prev_result.get("outcome")
    if not app_id:
        raise ValueError("application_id required")
    try:
        app = Application.objects.get(pk=app_id)
        correlation_id = app.correlation_id or None
        if outcome is None:
            score_row = app.score_result
            rules = list(PolicyRule.objects.filter(is_active=True).order_by("priority", "id"))
            ctx = {
                "score": decimal_to_float(score_row.score),
                "risk_band": score_row.risk_band,
                "features": app.feature_snapshot.data,
            }
            outcome = RuleEngine().evaluate(rules, ctx).outcome
        reason = f"Policy outcome: {outcome}"
        DecisionService.create_pipeline_decision(
            application=app,
            decision_type=outcome,
            score=app.score_result.score,
            risk_band=app.score_result.risk_band,
            reason_summary=reason,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        try:
            app = Application.objects.get(pk=app_id)
            cid = app.correlation_id
        except Application.DoesNotExist:
            cid = None
        _fail(app_id, exc, "persist_decision", cid)
        raise


@shared_task(
    bind=True,
    autoretry_for=(OperationalError, ConnectionError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def dispatch_webhook_placeholder(self, application_id: str):
    try:
        app = Application.objects.get(pk=application_id)
        correlation_id = app.correlation_id or None
        delivery = WebhookDelivery.objects.create(
            application=app,
            url=None,
            status=WebhookDeliveryStatus.SENT,
            payload={"application_id": str(app.id), "status": app.status},
            attempts=1,
        )
        AuditService.record(
            actor_type=ActorType.SYSTEM,
            actor_id=None,
            target_type="webhook_delivery",
            target_id=str(delivery.id),
            event_type=EventType.WEBHOOK_DISPATCH_ATTEMPT,
            correlation_id=correlation_id,
            metadata={"placeholder": True, "application_id": str(app.id)},
        )
    except Exception as exc:
        try:
            app = Application.objects.get(pk=application_id)
            cid = app.correlation_id
        except Application.DoesNotExist:
            cid = None
        AuditService.record(
            actor_type=ActorType.SYSTEM,
            actor_id=None,
            target_type="application",
            target_id=str(application_id),
            event_type=EventType.WEBHOOK_DISPATCH_ATTEMPT,
            correlation_id=cid,
            metadata={"error": str(exc)[:500], "placeholder": True},
        )
        logger.warning("webhook_placeholder_failed", extra={"application_id": application_id})


def enqueue_pipeline(application_id) -> None:
    from celery import chain

    aid = str(application_id)
    c = chain(
        enrich_application.si(aid),
        compute_features.si(aid),
        run_scoring.si(aid),
        evaluate_rules.si(aid),
        persist_decision.s(),
        dispatch_webhook_placeholder.si(aid),
    )
    c.apply_async()
