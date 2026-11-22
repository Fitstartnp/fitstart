from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.households.models import Household, HouseholdMembership


class PersonalRecord(models.Model):
    """Base for personal records; assigning a household explicitly opts into sharing."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_records",
    )
    household = models.ForeignKey(
        Household,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    sharing_preference: str | None = None

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if not self.household_id:
            return
        active_membership = HouseholdMembership.objects.filter(
            household_id=self.household_id,
            user_id=self.owner_id,
            status=HouseholdMembership.Status.ACTIVE,
        ).exists()
        if not active_membership:
            raise ValidationError({"household": "The record owner must be an active member of the selected household."})
        profile = getattr(self.owner, "personal_profile", None)
        if not self.sharing_preference or not profile or not getattr(profile, self.sharing_preference, False):
            raise ValidationError({"household": "The owner has not enabled sharing for this category."})

    @classmethod
    def visible_to(cls, user):
        """Private owner records plus explicitly shared records in active shared households."""
        if not user or not user.is_authenticated:
            return cls.objects.none()
        sharing = cls.sharing_preference
        if not sharing:
            return cls.objects.filter(owner=user)
        shared = Q(
            household__memberships__user=user,
            household__memberships__status=HouseholdMembership.Status.ACTIVE,
            owner__personal_profile__isnull=False,
            **{f"owner__personal_profile__{sharing}": True},
        )
        return cls.objects.filter(Q(owner=user) | shared).distinct()


class WeightEntry(PersonalRecord):
    sharing_preference = "share_weight_history"
    measured_on = models.DateField(default=timezone.localdate)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2)
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-measured_on", "-id")
        indexes = [models.Index(fields=("owner", "measured_on"))]

    def __str__(self):
        return f"{self.owner_id}: {self.weight_kg} kg on {self.measured_on}"


class BodyMeasurement(PersonalRecord):
    sharing_preference = "share_body_measurements"
    measured_at = models.DateTimeField(default=timezone.now)
    waist_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    hip_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    chest_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    neck_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    arm_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    thigh_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-measured_at", "-id")
        indexes = [models.Index(fields=("owner", "measured_at"))]


class FoodEntry(PersonalRecord):
    sharing_preference = "share_food_diary"

    class MealSlot(models.TextChoices):
        BREAKFAST = "breakfast", "Breakfast"
        LUNCH = "lunch", "Lunch"
        SNACK = "snack", "Snack"
        DINNER = "dinner", "Dinner"
        OTHER = "other", "Other"

    logged_at = models.DateTimeField(default=timezone.now)
    meal_slot = models.CharField(max_length=12, choices=MealSlot.choices, default=MealSlot.OTHER)
    food_name = models.CharField(max_length=180)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit = models.CharField(max_length=40, blank=True)
    calories_kcal = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    protein_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    carbs_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    fat_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    fiber_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-logged_at", "-id")
        indexes = [models.Index(fields=("owner", "logged_at"))]


class WaterEntry(PersonalRecord):
    sharing_preference = "share_water_logs"
    logged_at = models.DateTimeField(default=timezone.now)
    amount_ml = models.PositiveIntegerField()

    class Meta:
        ordering = ("-logged_at", "-id")
        indexes = [models.Index(fields=("owner", "logged_at"))]


class MealPlanEntry(PersonalRecord):
    sharing_preference = "share_meal_plans"

    class MealSlot(models.TextChoices):
        BREAKFAST = "breakfast", "Breakfast"
        LUNCH = "lunch", "Lunch"
        SNACK = "snack", "Snack"
        DINNER = "dinner", "Dinner"

    plan_date = models.DateField()
    meal_slot = models.CharField(max_length=12, choices=MealSlot.choices)
    title = models.CharField(max_length=180)
    servings = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    notes = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ("plan_date", "meal_slot", "id")
        indexes = [models.Index(fields=("owner", "plan_date"))]


class GroceryList(PersonalRecord):
    sharing_preference = "share_grocery_lists"
    name = models.CharField(max_length=120, default="Weekly groceries")
    week_of = models.DateField(default=timezone.localdate)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ("-week_of", "-id")


class GroceryItem(models.Model):
    grocery_list = models.ForeignKey(GroceryList, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=180)
    quantity = models.CharField(max_length=80, blank=True)
    category = models.CharField(max_length=80, blank=True)
    is_checked = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "name", "id")


class WorkoutSession(PersonalRecord):
    sharing_preference = "share_workout_history"
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=180)
    notes = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ("-started_at", "-id")
        indexes = [models.Index(fields=("owner", "started_at"))]

    def clean(self):
        super().clean()
        if self.ended_at and self.ended_at < self.started_at:
            raise ValidationError({"ended_at": "Workout end time cannot be before its start."})


class WorkoutSet(models.Model):
    session = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name="sets")
    exercise_key = models.CharField(max_length=100)
    exercise_name = models.CharField(max_length=180)
    set_number = models.PositiveSmallIntegerField()
    reps = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    distance_m = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    rpe = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("session", "exercise_key", "set_number", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("session", "exercise_key", "set_number"),
                name="uniq_exercise_set_per_session",
            )
        ]


class FastingSession(PersonalRecord):
    sharing_preference = "share_fasting_sessions"
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    target_hours = models.DecimalField(max_digits=4, decimal_places=1, default=16)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-started_at", "-id")

    def clean(self):
        super().clean()
        if self.ended_at and self.ended_at < self.started_at:
            raise ValidationError({"ended_at": "Fasting end time cannot be before its start."})


class Goal(PersonalRecord):
    sharing_preference = "share_goals"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=180)
    metric_key = models.CharField(max_length=60)
    start_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    target_value = models.DecimalField(max_digits=10, decimal_places=2)
    current_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=40, blank=True)
    starts_on = models.DateField(default=timezone.localdate)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ("status", "target_date", "id")
        indexes = [models.Index(fields=("owner", "status"))]
