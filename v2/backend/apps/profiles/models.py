from django.conf import settings
from django.db import models


class PersonalProfile(models.Model):
    class UnitSystem(models.TextChoices):
        METRIC = "metric", "Metric"
        IMPERIAL = "imperial", "Imperial"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_profile",
    )
    display_name = models.CharField(max_length=80, blank=True)
    unit_system = models.CharField(max_length=10, choices=UnitSystem.choices, default=UnitSystem.METRIC)
    timezone_name = models.CharField(max_length=64, default="Europe/Berlin")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Sharing defaults: potentially sensitive measurements, nutrition and activity remain private.
    share_meal_plans = models.BooleanField(default=False)
    share_grocery_lists = models.BooleanField(default=False)
    share_workout_plans = models.BooleanField(default=False)
    share_weight_history = models.BooleanField(default=False)
    share_body_measurements = models.BooleanField(default=False)
    share_food_diary = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.display_name or self.user.email
