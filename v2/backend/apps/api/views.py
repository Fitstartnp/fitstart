from django.db import connection
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.households.models import HouseholdMembership
from apps.profiles.models import PersonalProfile


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # No versions, host details, credentials, or user data are disclosed.
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return Response({"status": "ok"})


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = PersonalProfile.objects.filter(user=request.user).first()
        return Response(
            {
                "id": request.user.pk,
                "email": request.user.email,
                "email_verified": request.user.email_verified_at is not None,
                "display_name": profile.display_name if profile else "",
                "unit_system": profile.unit_system if profile else "metric",
            }
        )


class MyHouseholdsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        memberships = (
            HouseholdMembership.objects.filter(user=request.user, status=HouseholdMembership.Status.ACTIVE)
            .select_related("household")
            .order_by("household__name")
        )
        return Response(
            [
                {
                    "id": item.household_id,
                    "name": item.household.name,
                    "role": item.role,
                    "joined_at": item.joined_at,
                }
                for item in memberships
            ]
        )
