from django.contrib import admin

from apps.audits.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "event_type", "actor_type", "target_type", "target_id", "correlation_id")
    list_filter = ("event_type", "actor_type")
    search_fields = ("target_id", "correlation_id")
