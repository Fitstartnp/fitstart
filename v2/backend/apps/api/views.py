from django.conf import settings
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.core.mail import send_mail
from django.db import connection, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.households.models import Household, HouseholdInvitation, HouseholdMembership
from apps.households.services import accept_invitation, create_household, create_invitation
from apps.profiles.models import PersonalProfile
from apps.tracking.models import (
    BodyMeasurement,
    FastingSession,
    FoodEntry,
    Goal,
    GroceryList,
    MealPlanEntry,
    WaterEntry,
    WeightEntry,
    WorkoutSession,
    GroceryItem,
    WorkoutSet,
)
from .serializers import (
    BodyMeasurementSerializer,
    FastingSessionSerializer,
    FoodEntrySerializer,
    GoalSerializer,
    GroceryListSerializer,
    MealPlanEntrySerializer,
    WaterEntrySerializer,
    WeightEntrySerializer,
    WorkoutSessionSerializer,
    GroceryItemSerializer,
    WorkoutSetSerializer,
)


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


class HouseholdsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        memberships = (
            HouseholdMembership.objects.filter(user=request.user, status=HouseholdMembership.Status.ACTIVE)
            .select_related("household")
            .filter(household__archived_at__isnull=True)
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

    def post(self, request):
        name = str(request.data.get("name", "")).strip()
        if not name or len(name) > 100:
            raise ValidationError({"name": "Enter a household name (1–100 characters)."})
        household = create_household(owner=request.user, name=name)
        AuditEvent.objects.create(
            actor=request.user,
            event_type="household.created",
            target_type="household",
            target_id=str(household.pk),
        )
        return Response(
            {"id": household.pk, "name": household.name, "role": HouseholdMembership.Role.OWNER},
            status=201,
        )


class HouseholdInvitationCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, household_id: int):
        household = get_object_or_404(Household, pk=household_id, archived_at__isnull=True)
        email = str(request.data.get("email", "")).strip().lower()
        role = str(request.data.get("role", HouseholdInvitation.Role.MEMBER)).strip().lower()
        try:
            validate_email(email)
        except DjangoValidationError as exc:
            raise ValidationError({"email": "Enter a valid email address."}) from exc

        try:
            invitation, raw_token = create_invitation(
                actor=request.user,
                household=household,
                email=email,
                role=role,
            )
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=403)
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        invite_url = f"{settings.FITSTART_PUBLIC_URL.rstrip('/')}/invite/#{raw_token}"
        message = (
            f"You have been invited to join the FitStart household '{household.name}'.\n\n"
            f"Open this one-time invitation link to create an account or sign in: {invite_url}\n\n"
            "This invitation expires in 7 days. If you were not expecting it, ignore this email."
        )
        try:
            sent = send_mail(
                subject=f"FitStart invitation to {household.name}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            if sent != 1:
                raise RuntimeError("The mail backend did not accept the message.")
        except Exception:
            invitation.revoked_at = timezone.now()
            invitation.save(update_fields=("revoked_at",))
            return Response(
                {"detail": "The invitation email could not be sent. Check the server email configuration."},
                status=503,
            )

        AuditEvent.objects.create(
            actor=request.user,
            event_type="household.invitation_sent",
            target_type="household",
            target_id=str(household.pk),
            metadata={"role": role},
        )
        # Never return the raw invitation token to API callers or write it to audit metadata.
        return Response({"detail": "Invitation sent."}, status=201)


@method_decorator(csrf_protect, name="dispatch")
class AcceptInvitationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_token = str(request.data.get("token", "")).strip()
        if not raw_token or len(raw_token) > 128:
            raise ValidationError({"token": "A valid invitation token is required."})

        digest = HouseholdInvitation.digest_token(raw_token)
        with transaction.atomic():
            invitation = (
                HouseholdInvitation.objects.select_for_update()
                .select_related("household")
                .filter(token_digest=digest)
                .first()
            )
            if invitation is None or not invitation.is_usable:
                return Response({"detail": "This invitation is invalid, expired, or already used."}, status=400)

            if request.user.is_authenticated:
                user = request.user
            else:
                if User.objects.filter(email__iexact=invitation.invited_email).exists():
                    return Response(
                        {"detail": "An account already exists for this email. Sign in, then reopen the invitation link."},
                        status=409,
                    )
                password = request.data.get("password")
                if not isinstance(password, str) or not password:
                    raise ValidationError({"password": "Choose a password to create your FitStart account."})
                password_user = User(email=invitation.invited_email)
                try:
                    from django.contrib.auth.password_validation import validate_password
                    validate_password(password, user=password_user)
                except DjangoValidationError as exc:
                    raise ValidationError({"password": list(exc.messages)}) from exc
                user = User.objects.create_user(
                    email=invitation.invited_email,
                    password=password,
                    is_active=True,
                    email_verified_at=timezone.now(),
                )

            try:
                membership = accept_invitation(user=user, raw_token=raw_token)
            except PermissionDenied as exc:
                return Response({"detail": str(exc)}, status=403)

            AuditEvent.objects.create(
                actor=user,
                event_type="household.invitation_accepted",
                target_type="household",
                target_id=str(membership.household_id),
                metadata={"role": membership.role},
            )
            login(request, user)

        return Response(
            {
                "detail": "Invitation accepted.",
                "account": {"id": user.pk, "email": user.email},
                "household": {"id": membership.household_id, "name": membership.household.name},
            },
            status=201,
        )


class PersonalRecordViewSet(viewsets.ModelViewSet):
    """Shared reads are allowed by category policy; mutations remain owner-only."""

    permission_classes = [permissions.IsAuthenticated]
    record_model = None

    def get_queryset(self):
        model = self.record_model
        queryset = model.objects.select_related("owner", "household")
        if self.action in ("update", "partial_update", "destroy"):
            return queryset.filter(owner=self.request.user)
        return model.visible_to(self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class WeightEntryViewSet(PersonalRecordViewSet):
    record_model = WeightEntry
    serializer_class = WeightEntrySerializer


class BodyMeasurementViewSet(PersonalRecordViewSet):
    record_model = BodyMeasurement
    serializer_class = BodyMeasurementSerializer


class FoodEntryViewSet(PersonalRecordViewSet):
    record_model = FoodEntry
    serializer_class = FoodEntrySerializer


class WaterEntryViewSet(PersonalRecordViewSet):
    record_model = WaterEntry
    serializer_class = WaterEntrySerializer


class MealPlanEntryViewSet(PersonalRecordViewSet):
    record_model = MealPlanEntry
    serializer_class = MealPlanEntrySerializer


class GroceryListViewSet(PersonalRecordViewSet):
    record_model = GroceryList
    serializer_class = GroceryListSerializer


class WorkoutSessionViewSet(PersonalRecordViewSet):
    record_model = WorkoutSession
    serializer_class = WorkoutSessionSerializer


class FastingSessionViewSet(PersonalRecordViewSet):
    record_model = FastingSession
    serializer_class = FastingSessionSerializer


class GoalViewSet(PersonalRecordViewSet):
    record_model = Goal
    serializer_class = GoalSerializer


class MyProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile, _ = PersonalProfile.objects.get_or_create(user=request.user)
        return Response(
            {
                "display_name": profile.display_name,
                "unit_system": profile.unit_system,
                "timezone_name": profile.timezone_name,
                "sharing": {
                    "meal_plans": profile.share_meal_plans,
                    "grocery_lists": profile.share_grocery_lists,
                    "workout_plans": profile.share_workout_plans,
                    "workout_history": profile.share_workout_history,
                    "weight_history": profile.share_weight_history,
                    "body_measurements": profile.share_body_measurements,
                    "food_diary": profile.share_food_diary,
                    "water_logs": profile.share_water_logs,
                    "fasting_sessions": profile.share_fasting_sessions,
                    "goals": profile.share_goals,
                },
            }
        )

    def patch(self, request):
        allowed = {
            "display_name": "display_name",
            "unit_system": "unit_system",
            "timezone_name": "timezone_name",
            "share_meal_plans": "share_meal_plans",
            "share_grocery_lists": "share_grocery_lists",
            "share_workout_plans": "share_workout_plans",
            "share_workout_history": "share_workout_history",
            "share_weight_history": "share_weight_history",
            "share_body_measurements": "share_body_measurements",
            "share_food_diary": "share_food_diary",
            "share_water_logs": "share_water_logs",
            "share_fasting_sessions": "share_fasting_sessions",
            "share_goals": "share_goals",
        }
        unknown = set(request.data.keys()) - set(allowed)
        if unknown:
            raise ValidationError({"detail": f"Unsupported profile fields: {', '.join(sorted(unknown))}"})
        profile, _ = PersonalProfile.objects.get_or_create(user=request.user)
        for field in allowed:
            if field not in request.data:
                continue
            value = request.data[field]
            if field.startswith("share_") and not isinstance(value, bool):
                raise ValidationError({field: "Sharing settings must be true or false."})
            if field == "display_name" and (not isinstance(value, str) or len(value) > 80):
                raise ValidationError({field: "Display name must be 80 characters or fewer."})
            if field == "unit_system" and value not in ("metric", "imperial"):
                raise ValidationError({field: "Unit system must be metric or imperial."})
            if field == "timezone_name":
                from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
                try:
                    ZoneInfo(value)
                except (ZoneInfoNotFoundError, TypeError):
                    raise ValidationError({field: "Enter a valid IANA time zone."})
            setattr(profile, field, value)
        profile.full_clean()
        profile.save()
        return self.get(request)


class GroceryItemListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_parent(self, request, grocery_list_id):
        return get_object_or_404(
            GroceryList.visible_to(request.user),
            pk=grocery_list_id,
        )

    def get(self, request, grocery_list_id):
        parent = self.get_parent(request, grocery_list_id)
        items = parent.items.all()
        return Response(GroceryItemSerializer(items, many=True).data)

    def post(self, request, grocery_list_id):
        parent = self.get_parent(request, grocery_list_id)
        if parent.owner_id != request.user.pk:
            return Response({"detail": "Only the grocery list owner can add items."}, status=403)
        serializer = GroceryItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(grocery_list=parent)
        return Response(GroceryItemSerializer(item).data, status=201)


class GroceryItemDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_parent_and_item(self, request, grocery_list_id, item_id, owner_only=False):
        queryset = GroceryList.objects.filter(owner=request.user) if owner_only else GroceryList.visible_to(request.user)
        parent = get_object_or_404(queryset, pk=grocery_list_id)
        item = get_object_or_404(GroceryItem.objects.filter(grocery_list=parent), pk=item_id)
        return parent, item

    def get(self, request, grocery_list_id, item_id):
        _, item = self.get_parent_and_item(request, grocery_list_id, item_id)
        return Response(GroceryItemSerializer(item).data)

    def patch(self, request, grocery_list_id, item_id):
        _, item = self.get_parent_and_item(request, grocery_list_id, item_id, owner_only=True)
        serializer = GroceryItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(GroceryItemSerializer(item).data)

    def delete(self, request, grocery_list_id, item_id):
        _, item = self.get_parent_and_item(request, grocery_list_id, item_id, owner_only=True)
        item.delete()
        return Response(status=204)


class WorkoutSetListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_parent(self, request, session_id):
        return get_object_or_404(WorkoutSession.visible_to(request.user), pk=session_id)

    def get(self, request, session_id):
        parent = self.get_parent(request, session_id)
        return Response(WorkoutSetSerializer(parent.sets.all(), many=True).data)

    def post(self, request, session_id):
        parent = self.get_parent(request, session_id)
        if parent.owner_id != request.user.pk:
            return Response({"detail": "Only the workout owner can add sets."}, status=403)
        serializer = WorkoutSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(session=parent)
        return Response(WorkoutSetSerializer(record).data, status=201)


class WorkoutSetDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_parent_and_set(self, request, session_id, set_id, owner_only=False):
        queryset = WorkoutSession.objects.filter(owner=request.user) if owner_only else WorkoutSession.visible_to(request.user)
        parent = get_object_or_404(queryset, pk=session_id)
        record = get_object_or_404(WorkoutSet.objects.filter(session=parent), pk=set_id)
        return parent, record

    def get(self, request, session_id, set_id):
        _, record = self.get_parent_and_set(request, session_id, set_id)
        return Response(WorkoutSetSerializer(record).data)

    def patch(self, request, session_id, set_id):
        _, record = self.get_parent_and_set(request, session_id, set_id, owner_only=True)
        serializer = WorkoutSetSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(WorkoutSetSerializer(record).data)

    def delete(self, request, session_id, set_id):
        _, record = self.get_parent_and_set(request, session_id, set_id, owner_only=True)
        record.delete()
        return Response(status=204)
