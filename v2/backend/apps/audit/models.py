from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """Security/admin event metadata only; never store health payloads or secrets here."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    event_type = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-occurred_at",)

    def __str__(self) -> str:
        return f"{self.event_type} at {self.occurred_at:%Y-%m-%d %H:%M:%S}"



class DataImportBatch(models.Model):
    """Stores import provenance and counts, never the raw health-data backup."""

    class SourceProfile(models.TextChoices):
        HUSBAND = "husband", "Husband"
        WIFE = "wife", "Wife"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="data_import_batches",
    )
    source_profile = models.CharField(max_length=10, choices=SourceProfile.choices)
    fingerprint = models.CharField(max_length=64)
    counts = models.JSONField(default=dict)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-imported_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("actor", "fingerprint"),
                name="uniq_user_data_import_fingerprint",
            )
        ]

    def __str__(self):
        return f"V1 import ({self.source_profile}) for user {self.actor_id}"
