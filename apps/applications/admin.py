from django.contrib import admin

from apps.applications.models import Application, FeatureSnapshot


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "principal_kind", "created_at")
    list_filter = ("status", "principal_kind")


@admin.register(FeatureSnapshot)
class FeatureSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "version", "created_at")
