from django.urls import path

from .views import HealthView, MeView, MyHouseholdsView

urlpatterns = [
    path("health/", HealthView.as_view(), name="api-health"),
    path("me/", MeView.as_view(), name="api-me"),
    path("households/", MyHouseholdsView.as_view(), name="api-my-households"),
]
