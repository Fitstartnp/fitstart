from django.urls import path

from .views import (
    AcceptInvitationView,
    HealthView,
    HouseholdInvitationCreateView,
    HouseholdsView,
    MeView,
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="api-health"),
    path("me/", MeView.as_view(), name="api-me"),
    path("households/", HouseholdsView.as_view(), name="api-households"),
    path(
        "households/<int:household_id>/invitations/",
        HouseholdInvitationCreateView.as_view(),
        name="api-household-invitation-create",
    ),
    path("invitations/accept/", AcceptInvitationView.as_view(), name="api-invitation-accept"),
]
