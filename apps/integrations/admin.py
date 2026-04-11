from django.contrib import admin

from apps.integrations.models import WebhookDelivery


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("application", "status", "attempts", "created_at")
