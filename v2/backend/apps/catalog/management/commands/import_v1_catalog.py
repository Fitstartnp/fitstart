import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Exercise, Recipe, RoutineExercise, WorkoutRoutine


class Command(BaseCommand):
    help = "Idempotently import the original FitStart V1 recipe and exercise catalogue."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default=None,
            help="Optional path to a V1 catalog JSON file.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source = Path(options["source"]) if options.get("source") else (
            Path(__file__).resolve().parents[4] / "catalogs" / "v1-catalog.json"
        )
        if not source.is_file():
            raise CommandError(f"Catalog source file not found: {source}")
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read V1 catalog: {exc}") from exc

        meal_db = data.get("mealDatabase")
        workout_db = data.get("workoutDatabase")
        if not isinstance(meal_db, dict) or not isinstance(workout_db, dict):
            raise CommandError("Catalog JSON must contain mealDatabase and workoutDatabase objects.")

        recipes_created = recipes_updated = 0
        for diet_style, menus in meal_db.items():
            if not isinstance(menus, list):
                raise CommandError(f"Recipe menus for {diet_style} must be a list.")
            for menu_index, menu in enumerate(menus, start=1):
                if not isinstance(menu, list):
                    raise CommandError(f"Recipe menu {diet_style}/{menu_index} is invalid.")
                for slot_index, meal in enumerate(menu, start=1):
                    if not isinstance(meal, dict) or not meal.get("name"):
                        raise CommandError(f"Recipe record {diet_style}/{menu_index}/{slot_index} is invalid.")
                    defaults = {
                        "slot": meal.get("slot", "Other"),
                        "icon": str(meal.get("icon", ""))[:16],
                        "ratio": meal.get("ratio", 0),
                        "base_calories_kcal": meal.get("baseKcal", 0),
                        "name": str(meal["name"])[:180],
                        "prep_time": str(meal.get("prepTime", ""))[:20],
                        "cook_time": str(meal.get("cookTime", ""))[:20],
                        "portions": meal.get("portions", []),
                        "base_macros": meal.get("baseMacros", {}),
                        "steps": meal.get("steps", []),
                        "tip": meal.get("tip", ""),
                        "source": "fitstart-v1",
                    }
                    _, created = Recipe.objects.update_or_create(
                        diet_style=diet_style,
                        menu_number=menu_index,
                        slot_position=slot_index,
                        defaults=defaults,
                    )
                    recipes_created += int(created)
                    recipes_updated += int(not created)

        exercises_created = exercises_updated = 0
        routines_created = routines_updated = 0
        routine_links = 0
        for mode, levels in workout_db.items():
            if not isinstance(levels, dict):
                raise CommandError(f"Workout modes for {mode} are invalid.")
            for level, routines in levels.items():
                if not isinstance(routines, list):
                    raise CommandError(f"Workout routines for {mode}/{level} are invalid.")
                for variation_index, exercises in enumerate(routines):
                    routine, created = WorkoutRoutine.objects.update_or_create(
                        mode=mode,
                        level=level,
                        variation_index=variation_index,
                        defaults={
                            "title": f"{mode.title()} · {level.title()} · Routine {variation_index + 1}",
                            "source": "fitstart-v1",
                        },
                    )
                    routines_created += int(created)
                    routines_updated += int(not created)
                    routine.exercise_links.all().delete()
                    for position, exercise_data in enumerate(exercises, start=1):
                        source_key = str(exercise_data.get("id", "")).strip()
                        if not source_key or not exercise_data.get("name"):
                            raise CommandError(f"Exercise in {mode}/{level} routine {variation_index + 1} is invalid.")
                        exercise, exercise_created = Exercise.objects.update_or_create(
                            source_key=source_key,
                            defaults={
                                "name": str(exercise_data["name"])[:180],
                                "detail": str(exercise_data.get("detail", ""))[:300],
                                "estimated_calories_kcal": max(0, int(exercise_data.get("kcal", 0) or 0)),
                                "focus": str(exercise_data.get("focus", ""))[:120],
                                "muscles": str(exercise_data.get("muscles", ""))[:240],
                                "steps": exercise_data.get("steps", []),
                                "modification": exercise_data.get("mod", ""),
                                "common_mistake": exercise_data.get("mistake", ""),
                                "source": "fitstart-v1",
                            },
                        )
                        exercises_created += int(exercise_created)
                        exercises_updated += int(not exercise_created)
                        RoutineExercise.objects.create(
                            routine=routine,
                            exercise=exercise,
                            position=position,
                        )
                        routine_links += 1

        self.stdout.write(self.style.SUCCESS(
            "V1 catalog import complete: "
            f"{recipes_created} recipes created, {recipes_updated} updated; "
            f"{exercises_created} exercises created, {exercises_updated} updated; "
            f"{routines_created} routines created, {routines_updated} updated; "
            f"{routine_links} routine links rebuilt."
        ))
