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
