from django.contrib import admin

from apps.decisions.models import Decision


@admin.register(Decision)
class DecisionAdmin(admin.ModelAdmin):
    list_display = ("application", "decision_type", "source", "is_current", "created_at")
    list_filter = ("decision_type", "source", "is_current")
