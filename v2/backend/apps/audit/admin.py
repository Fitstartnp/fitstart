from django.contrib import admin

from .models import AuditEvent, DataImportBatch


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "actor", "target_type", "target_id", "occurred_at")
    list_filter = ("event_type", "occurred_at")
    search_fields = ("actor__email", "target_type", "target_id")
    readonly_fields = ("actor", "event_type", "target_type", "target_id", "metadata", "occurred_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DataImportBatch)
class DataImportBatchAdmin(admin.ModelAdmin):
    list_display = ("actor", "source_profile", "imported_at")
    search_fields = ("actor__email", "fingerprint")
    readonly_fields = ("actor", "source_profile", "fingerprint", "counts", "imported_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
