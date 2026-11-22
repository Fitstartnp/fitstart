from django.contrib import admin

from .models import (
    BodyMeasurement,
    FastingSession,
    FoodEntry,
    Goal,
    GroceryItem,
    GroceryList,
    MealPlanEntry,
    WaterEntry,
    WeightEntry,
    WorkoutSession,
    WorkoutSet,
)


@admin.register(WeightEntry, BodyMeasurement, FoodEntry, WaterEntry, MealPlanEntry, GroceryList, WorkoutSession, FastingSession, Goal)
class PersonalRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "household", "created_at")
    list_filter = ("created_at",)
    search_fields = ("owner__email",)
    readonly_fields = ("created_at", "updated_at")


class GroceryItemInline(admin.TabularInline):
    model = GroceryItem
    extra = 0


@admin.register(GroceryItem)
class GroceryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "grocery_list", "quantity", "is_checked")
    search_fields = ("name", "grocery_list__owner__email")


@admin.register(WorkoutSet)
class WorkoutSetAdmin(admin.ModelAdmin):
    list_display = ("session", "exercise_name", "set_number", "reps", "weight_kg")
    search_fields = ("exercise_name", "session__owner__email")
