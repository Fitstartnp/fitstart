from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Exercise, Recipe, RoutineExercise, WorkoutRoutine


class CatalogImportTests(TestCase):
    def test_import_v1_catalog_is_idempotent_and_loads_expected_counts(self):
        call_command("import_v1_catalog")
        first_counts = (
            Recipe.objects.count(),
            Exercise.objects.count(),
            WorkoutRoutine.objects.count(),
            RoutineExercise.objects.count(),
        )
        self.assertEqual(first_counts, (160, 80, 16, 80))

        call_command("import_v1_catalog")
        second_counts = (
            Recipe.objects.count(),
            Exercise.objects.count(),
            WorkoutRoutine.objects.count(),
            RoutineExercise.objects.count(),
        )
        self.assertEqual(second_counts, first_counts)

        breakfast = Recipe.objects.get(
            diet_style="balanced",
            menu_number=1,
            slot_position=1,
        )
        self.assertEqual(breakfast.name, "Oatmeal Power Bowl & Boiled Egg")
        self.assertEqual(len(breakfast.steps), 3)
        routine = WorkoutRoutine.objects.get(mode="home", level="beginner", variation_index=0)
        self.assertEqual(routine.exercise_links.count(), 5)
