from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PersonalProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_personal_profile(sender, instance, created, **kwargs):
    if created:
        PersonalProfile.objects.get_or_create(user=instance)
