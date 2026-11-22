from rest_framework.routers import DefaultRouter
from django.urls import include, path

from .views import (
    AcceptInvitationView,
    BodyMeasurementViewSet,
    FastingSessionViewSet,
    FoodEntryViewSet,
    GoalViewSet,
    GroceryItemDetailView,
    GroceryItemListView,
    GroceryListViewSet,
    HealthView,
    HouseholdInvitationCreateView,
    HouseholdsView,
    MeView,
    MealPlanEntryViewSet,
    MyProfileView,
    MyDataExportView,
    WaterEntryViewSet,
    WeightEntryViewSet,
    RecipeViewSet,
    ExerciseViewSet,
    WorkoutRoutineViewSet,
    RecipeFavoritesView,
    RecipeFavoriteDetailView,
    V1ImportCommitView,
    V1ImportPreviewView,
    WorkoutSessionViewSet,
    WorkoutSetDetailView,
    WorkoutSetListView,
)

router = DefaultRouter()
router.register("recipes", RecipeViewSet, basename="recipe")
router.register("exercises", ExerciseViewSet, basename="exercise")
router.register("workout-routines", WorkoutRoutineViewSet, basename="workout-routine")
router.register("weight-entries", WeightEntryViewSet, basename="weight-entry")
router.register("body-measurements", BodyMeasurementViewSet, basename="body-measurement")
router.register("food-entries", FoodEntryViewSet, basename="food-entry")
router.register("water-entries", WaterEntryViewSet, basename="water-entry")
router.register("meal-plan-entries", MealPlanEntryViewSet, basename="meal-plan-entry")
router.register("grocery-lists", GroceryListViewSet, basename="grocery-list")
router.register("workout-sessions", WorkoutSessionViewSet, basename="workout-session")
router.register("fasting-sessions", FastingSessionViewSet, basename="fasting-session")
router.register("goals", GoalViewSet, basename="goal")

urlpatterns = [
    path("recipes/favorites/", RecipeFavoritesView.as_view(), name="api-recipe-favorites"),
    path("recipes/favorites/<int:recipe_id>/", RecipeFavoriteDetailView.as_view(), name="api-recipe-favorite-detail"),
    path("grocery-lists/<int:grocery_list_id>/items/", GroceryItemListView.as_view(), name="api-grocery-items"),
    path("grocery-lists/<int:grocery_list_id>/items/<int:item_id>/", GroceryItemDetailView.as_view(), name="api-grocery-item-detail"),
    path("workout-sessions/<int:session_id>/sets/", WorkoutSetListView.as_view(), name="api-workout-sets"),
    path("workout-sessions/<int:session_id>/sets/<int:set_id>/", WorkoutSetDetailView.as_view(), name="api-workout-set-detail"),
    path("imports/v1/preview/", V1ImportPreviewView.as_view(), name="api-v1-import-preview"),
    path("imports/v1/commit/", V1ImportCommitView.as_view(), name="api-v1-import-commit"),
    path("imports/v1/preview/", V1ImportPreviewView.as_view(), name="api-v1-import-preview"),
    path("imports/v1/commit/", V1ImportCommitView.as_view(), name="api-v1-import-commit"),
    path("export/", MyDataExportView.as_view(), name="api-data-export"),
    path("health/", HealthView.as_view(), name="api-health"),
    path("me/", MeView.as_view(), name="api-me"),
    path("profile/", MyProfileView.as_view(), name="api-profile"),
    path("households/", HouseholdsView.as_view(), name="api-households"),
    path(
        "households/<int:household_id>/invitations/",
        HouseholdInvitationCreateView.as_view(),
        name="api-household-invitation-create",
    ),
    path("invitations/accept/", AcceptInvitationView.as_view(), name="api-invitation-accept"),
    path("", include(router.urls)),
]
