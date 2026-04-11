from django.core.management.base import BaseCommand

from apps.policies.models import PolicyOutcome, PolicyRule


class Command(BaseCommand):
    help = "Seed default policy rules (idempotent by name)."

    def handle(self, *args, **options):
        defaults = [
            {
                "name": "Decline high risk band",
                "priority": 10,
                "is_active": True,
                "condition": {"risk_band": "high"},
                "outcome": PolicyOutcome.DECLINED,
            },
            {
                "name": "Manual review high score",
                "priority": 20,
                "is_active": True,
                "condition": {"min_score": 85},
                "outcome": PolicyOutcome.MANUAL_REVIEW,
            },
            {
                "name": "Approve low risk",
                "priority": 100,
                "is_active": True,
                "condition": {"risk_band": "low", "max_score": 100},
                "outcome": PolicyOutcome.APPROVED,
            },
            {
                "name": "Catch-all manual review",
                "priority": 1000,
                "is_active": True,
                "condition": {},
                "outcome": PolicyOutcome.MANUAL_REVIEW,
            },
        ]
        for row in defaults:
            obj, created = PolicyRule.objects.update_or_create(
                name=row["name"],
                defaults={
                    "priority": row["priority"],
                    "is_active": row["is_active"],
                    "condition": row["condition"],
                    "outcome": row["outcome"],
                },
            )
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} rule: {obj.name}"))
