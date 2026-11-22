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
    WaterEntryViewSet,
    WeightEntryViewSet,
    WorkoutSessionViewSet,
    WorkoutSetDetailView,
    WorkoutSetListView,
)

router = DefaultRouter()
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
    path("grocery-lists/<int:grocery_list_id>/items/", GroceryItemListView.as_view(), name="api-grocery-items"),
    path("grocery-lists/<int:grocery_list_id>/items/<int:item_id>/", GroceryItemDetailView.as_view(), name="api-grocery-item-detail"),
    path("workout-sessions/<int:session_id>/sets/", WorkoutSetListView.as_view(), name="api-workout-sets"),
    path("workout-sessions/<int:session_id>/sets/<int:set_id>/", WorkoutSetDetailView.as_view(), name="api-workout-set-detail"),
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
