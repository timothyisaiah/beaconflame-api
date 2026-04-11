from django.contrib import admin

from apps.scoring.models import ScoreResult


@admin.register(ScoreResult)
class ScoreResultAdmin(admin.ModelAdmin):
    list_display = ("application", "score", "risk_band", "engine_version", "created_at")
