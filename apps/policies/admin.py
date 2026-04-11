from django.contrib import admin

from apps.policies.models import PolicyRule


@admin.register(PolicyRule)
class PolicyRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "priority", "is_active", "outcome", "updated_at")
    list_filter = ("is_active", "outcome")
