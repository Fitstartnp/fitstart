from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


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
    age = models.PositiveSmallIntegerField(default=30, validators=[MinValueValidator(15), MaxValueValidator(100)])
    gender = models.CharField(
        max_length=12,
        choices=(("male", "Male"), ("female", "Female"), ("other", "Other")),
        default="male",
    )
    height_cm = models.DecimalField(
        max_digits=5, decimal_places=2, default=175,
        validators=[MinValueValidator(100), MaxValueValidator(250)],
    )
    start_weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, default=86,
        validators=[MinValueValidator(30), MaxValueValidator(400)],
    )
    current_weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, default=86,
        validators=[MinValueValidator(30), MaxValueValidator(400)],
    )
    goal_weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, default=75,
        validators=[MinValueValidator(30), MaxValueValidator(400)],
    )
    activity_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.375,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
    )
    daily_deficit_kcal = models.PositiveSmallIntegerField(
        default=500, validators=[MaxValueValidator(1500)]
    )
    diet_type = models.CharField(max_length=30, default="balanced")
    workout_mode = models.CharField(
        max_length=12, choices=(("home", "Home"), ("gym", "Gym")), default="home"
    )
    fitness_level = models.CharField(
        max_length=16,
        choices=(("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced")),
        default="beginner",
    )
    # V1-compatible planner state retained per account during migration.
    meal_variation_index = models.PositiveSmallIntegerField(default=0)
    slot_offsets = models.JSONField(default=dict, blank=True)
    workout_variation_index = models.PositiveSmallIntegerField(default=0)
    exercise_offsets = models.JSONField(default=dict, blank=True)
    completed_exercises = models.JSONField(default=dict, blank=True)
    streak_count = models.PositiveIntegerField(default=1)
    last_active_date = models.DateField(null=True, blank=True)
    fasting_protocol_hours = models.PositiveSmallIntegerField(default=16)
    fasting_is_active = models.BooleanField(default=False)
    fasting_elapsed_minutes = models.PositiveSmallIntegerField(default=0)
    legacy_favorite_recipe_names = models.JSONField(default=list, blank=True)
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
    share_water_logs = models.BooleanField(default=False)
    share_workout_history = models.BooleanField(default=False)
    share_fasting_sessions = models.BooleanField(default=False)
    share_goals = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.display_name or self.user.email
