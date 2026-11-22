from django.contrib import admin

from .models import Exercise, Recipe, RecipeFavorite, RoutineExercise, WorkoutRoutine


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("name", "diet_style", "menu_number", "slot", "base_calories_kcal")
    list_filter = ("diet_style", "slot")
    search_fields = ("name",)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "source_key", "focus", "estimated_calories_kcal")
    search_fields = ("name", "source_key", "focus", "muscles")


class RoutineExerciseInline(admin.TabularInline):
    model = RoutineExercise
    extra = 0
    autocomplete_fields = ("exercise",)


@admin.register(WorkoutRoutine)
class WorkoutRoutineAdmin(admin.ModelAdmin):
    list_display = ("title", "mode", "level", "variation_index")
    list_filter = ("mode", "level")
    inlines = (RoutineExerciseInline,)


@admin.register(RecipeFavorite)
class RecipeFavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "recipe", "created_at")
    search_fields = ("user__email", "recipe__name")
    readonly_fields = ("created_at",)
