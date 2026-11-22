from django.conf import settings
from django.db import models


class Recipe(models.Model):
    class DietStyle(models.TextChoices):
        BALANCED = "balanced", "Balanced"
        VEGETARIAN = "vegetarian", "Vegetarian"
        HIGH_PROTEIN = "high_protein", "High protein"
        LOW_CARB = "low_carb", "Low carb"

    class MealSlot(models.TextChoices):
        BREAKFAST = "Breakfast", "Breakfast"
        LUNCH = "Lunch", "Lunch"
        SNACK = "Snack", "Snack"
        DINNER = "Dinner", "Dinner"

    diet_style = models.CharField(max_length=20, choices=DietStyle.choices)
    menu_number = models.PositiveSmallIntegerField()
    slot_position = models.PositiveSmallIntegerField()
    slot = models.CharField(max_length=12, choices=MealSlot.choices)
    icon = models.CharField(max_length=16, blank=True)
    ratio = models.DecimalField(max_digits=4, decimal_places=2)
    base_calories_kcal = models.PositiveIntegerField()
    name = models.CharField(max_length=180)
    prep_time = models.CharField(max_length=20, blank=True)
    cook_time = models.CharField(max_length=20, blank=True)
    portions = models.JSONField(default=list)
    base_macros = models.JSONField(default=dict)
    steps = models.JSONField(default=list)
    tip = models.TextField(blank=True)
    source = models.CharField(max_length=24, default="fitstart-v1")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("diet_style", "menu_number", "slot_position")
        constraints = [
            models.UniqueConstraint(
                fields=("diet_style", "menu_number", "slot_position"),
                name="uniq_recipe_diet_menu_slot",
            )
        ]
        indexes = [
            models.Index(fields=("diet_style", "slot")),
            models.Index(fields=("name",)),
        ]

    def __str__(self):
        return f"{self.name} ({self.diet_style})"


class Exercise(models.Model):
    source_key = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=180)
    detail = models.CharField(max_length=300, blank=True)
    estimated_calories_kcal = models.PositiveIntegerField(default=0)
    focus = models.CharField(max_length=120, blank=True)
    muscles = models.CharField(max_length=240, blank=True)
    steps = models.JSONField(default=list)
    modification = models.TextField(blank=True)
    common_mistake = models.TextField(blank=True)
    source = models.CharField(max_length=24, default="fitstart-v1")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class WorkoutRoutine(models.Model):
    class Mode(models.TextChoices):
        HOME = "home", "Home"
        GYM = "gym", "Gym"

    class Level(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"

    mode = models.CharField(max_length=8, choices=Mode.choices)
    level = models.CharField(max_length=16, choices=Level.choices)
    variation_index = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=120)
    exercises = models.ManyToManyField(
        Exercise,
        through="RoutineExercise",
        related_name="routines",
    )
    source = models.CharField(max_length=24, default="fitstart-v1")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("mode", "level", "variation_index")
        constraints = [
            models.UniqueConstraint(
                fields=("mode", "level", "variation_index"),
                name="uniq_workout_routine_variant",
            )
        ]

    def __str__(self):
        return self.title


class RoutineExercise(models.Model):
    routine = models.ForeignKey(WorkoutRoutine, on_delete=models.CASCADE, related_name="exercise_links")
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="routine_links")
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(
                fields=("routine", "position"),
                name="uniq_exercise_position_per_routine",
            )
        ]


class RecipeFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipe_favorites")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="favorites")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("user", "recipe"), name="uniq_recipe_favorite_per_user")
        ]

    def __str__(self):
        return f"{self.user_id} favorite {self.recipe_id}"
