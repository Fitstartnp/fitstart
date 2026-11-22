import hashlib
import json
from datetime import datetime, time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

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
from rest_framework import mixins, permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.models import AuditEvent, DataImportBatch
from apps.catalog.models import Exercise, Recipe, RecipeFavorite, WorkoutRoutine
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
    RecipeSerializer,
    ExerciseSerializer,
    WorkoutRoutineSerializer,
    RecipeFavoriteSerializer,
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

    def _sync_current_weight(self):
        latest = WeightEntry.objects.filter(owner=self.request.user).order_by("-measured_on", "-id").first()
        profile, _ = PersonalProfile.objects.get_or_create(user=self.request.user)
        profile.current_weight_kg = latest.weight_kg if latest else profile.start_weight_kg
        profile.save(update_fields=("current_weight_kg", "updated_at"))

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._sync_current_weight()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._sync_current_weight()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self._sync_current_weight()


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
                "age": profile.age,
                "gender": profile.gender,
                "height_cm": profile.height_cm,
                "start_weight_kg": profile.start_weight_kg,
                "current_weight_kg": profile.current_weight_kg,
                "goal_weight_kg": profile.goal_weight_kg,
                "activity_multiplier": profile.activity_multiplier,
                "daily_deficit_kcal": profile.daily_deficit_kcal,
                "diet_type": profile.diet_type,
                "workout_mode": profile.workout_mode,
                "fitness_level": profile.fitness_level,
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
            "age": "age",
            "gender": "gender",
            "height_cm": "height_cm",
            "start_weight_kg": "start_weight_kg",
            "current_weight_kg": "current_weight_kg",
            "goal_weight_kg": "goal_weight_kg",
            "activity_multiplier": "activity_multiplier",
            "daily_deficit_kcal": "daily_deficit_kcal",
            "diet_type": "diet_type",
            "workout_mode": "workout_mode",
            "fitness_level": "fitness_level",
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
        try:
            profile.full_clean()
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", exc.messages)) from exc
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


class MyDataExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        profile, _ = PersonalProfile.objects.get_or_create(user=user)

        def serialize(queryset, serializer_class):
            return serializer_class(queryset, many=True).data

        weight_records = WeightEntry.objects.filter(owner=user).order_by("measured_on", "id")
        body_records = BodyMeasurement.objects.filter(owner=user).order_by("measured_at", "id")
        food_records = FoodEntry.objects.filter(owner=user).order_by("logged_at", "id")
        water_records = WaterEntry.objects.filter(owner=user).order_by("logged_at", "id")
        meal_records = MealPlanEntry.objects.filter(owner=user).order_by("plan_date", "id")
        grocery_records = GroceryList.objects.filter(owner=user).prefetch_related("items")
        workout_records = WorkoutSession.objects.filter(owner=user).prefetch_related("sets")
        fasting_records = FastingSession.objects.filter(owner=user).order_by("started_at", "id")
        goal_records = Goal.objects.filter(owner=user).order_by("created_at", "id")

        payload = {
            "format": "fitstart-v2-export",
            "version": 1,
            "exported_at": timezone.now(),
            "account": {"email": user.email},
            "profile": {
                "display_name": profile.display_name,
                "unit_system": profile.unit_system,
                "timezone_name": profile.timezone_name,
                "age": profile.age,
                "gender": profile.gender,
                "height_cm": profile.height_cm,
                "start_weight_kg": profile.start_weight_kg,
                "current_weight_kg": profile.current_weight_kg,
                "goal_weight_kg": profile.goal_weight_kg,
                "activity_multiplier": profile.activity_multiplier,
                "daily_deficit_kcal": profile.daily_deficit_kcal,
                "diet_type": profile.diet_type,
                "workout_mode": profile.workout_mode,
                "fitness_level": profile.fitness_level,
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
            },
            "records": {
                "weight_entries": serialize(weight_records, WeightEntrySerializer),
                "body_measurements": serialize(body_records, BodyMeasurementSerializer),
                "food_entries": serialize(food_records, FoodEntrySerializer),
                "water_entries": serialize(water_records, WaterEntrySerializer),
                "meal_plan_entries": serialize(meal_records, MealPlanEntrySerializer),
                "grocery_lists": [
                    {
                        **GroceryListSerializer(item).data,
                        "items": GroceryItemSerializer(item.items.all(), many=True).data,
                    }
                    for item in grocery_records
                ],
                "workout_sessions": [
                    {
                        **WorkoutSessionSerializer(item).data,
                        "sets": WorkoutSetSerializer(item.sets.all(), many=True).data,
                    }
                    for item in workout_records
                ],
                "fasting_sessions": serialize(fasting_records, FastingSessionSerializer),
                "goals": serialize(goal_records, GoalSerializer),
            },
        }
        response = Response(payload)
        response["Content-Disposition"] = 'attachment; filename="fitstart-v2-export.json"'
        response["Cache-Control"] = "no-store"
        return response


def _v1_decimal(value, *, minimum=Decimal("0"), maximum=Decimal("1000000")):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not result.is_finite() or result < minimum or result > maximum:
        return None
    return result


def _v1_int(value, *, minimum=0, maximum=1000000):
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number != number.to_integral_value():
        return None
    result = int(number)
    if result < minimum or result > maximum:
        return None
    return result


def _v1_import_plan(request, *, backup, profile_id):
    if not isinstance(backup, dict) or not isinstance(backup.get("profiles"), dict):
        raise ValidationError({"backup": "Choose a valid FitStart V1 JSON backup containing profiles."})
    if profile_id not in ("husband", "wife"):
        raise ValidationError({"profile_id": "Choose either the husband or wife profile."})
    raw = backup["profiles"].get(profile_id)
    if not isinstance(raw, dict):
        raise ValidationError({"profile_id": "That profile is not present in the selected backup."})

    weight_logs = raw.get("weightLogs", [])
    food_diary = raw.get("foodDiary", [])
    if not isinstance(weight_logs, list) or not isinstance(food_diary, list):
        raise ValidationError({"backup": "The selected profile has an invalid weight or food log."})
    if len(weight_logs) > 5000 or len(food_diary) > 5000:
        raise ValidationError({"backup": "This backup exceeds the 5,000-entry per-log import limit."})

    weights = []
    measurements = []
    invalid_weights = 0
    for entry in weight_logs:
        if not isinstance(entry, dict):
            invalid_weights += 1
            continue
        kg = _v1_decimal(entry.get("weightKg"), minimum=Decimal("0.1"), maximum=Decimal("400"))
        try:
            measured_on = datetime.strptime(str(entry.get("date", "")), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            measured_on = None
        if kg is None or measured_on is None:
            invalid_weights += 1
            continue
        weights.append({
            "measured_on": measured_on,
            "weight_kg": kg,
            "note": str(entry.get("note", ""))[:500],
        })
        waist = _v1_decimal(entry.get("waistCm"), minimum=Decimal("0.1"), maximum=Decimal("300"))
        if waist is not None:
            local_noon = datetime.combine(measured_on, time(12, 0))
            measurements.append({
                "measured_at": timezone.make_aware(local_noon, timezone.get_current_timezone()),
                "waist_cm": waist,
            })

    foods = []
    invalid_foods = 0
    for entry in food_diary:
        if not isinstance(entry, dict) or not str(entry.get("name", "")).strip():
            invalid_foods += 1
            continue
        calories = _v1_decimal(entry.get("kcal"), minimum=Decimal("0"), maximum=Decimal("100000"))
        protein = _v1_decimal(entry.get("p", 0), minimum=Decimal("0"), maximum=Decimal("10000"))
        carbs = _v1_decimal(entry.get("c", 0), minimum=Decimal("0"), maximum=Decimal("10000"))
        fat = _v1_decimal(entry.get("f", 0), minimum=Decimal("0"), maximum=Decimal("10000"))
        fiber = _v1_decimal(entry.get("fib", 0), minimum=Decimal("0"), maximum=Decimal("10000"))
        foods.append({
            "food_name": str(entry["name"]).strip()[:180],
            "calories_kcal": calories,
            "protein_g": protein,
            "carbs_g": carbs,
            "fat_g": fat,
            "fiber_g": fiber,
        })

    glasses = raw.get("waterGlasses", 0)
    if isinstance(glasses, bool):
        glasses = 0
    try:
        glasses = max(0, min(int(glasses), 40))
    except (TypeError, ValueError):
        glasses = 0

    metric_fields = {
        "name": ("display_name", lambda v: str(v)[:80]),
        "age": ("age", lambda v: int(v)),
        "gender": ("gender", lambda v: v if v in ("male", "female", "other") else "other"),
        "heightCm": ("height_cm", lambda v: _v1_decimal(v, minimum=Decimal("100"), maximum=Decimal("250"))),
        "startWeightKg": ("start_weight_kg", lambda v: _v1_decimal(v, minimum=Decimal("30"), maximum=Decimal("400"))),
        "currentWeightKg": ("current_weight_kg", lambda v: _v1_decimal(v, minimum=Decimal("30"), maximum=Decimal("400"))),
        "goalWeightKg": ("goal_weight_kg", lambda v: _v1_decimal(v, minimum=Decimal("30"), maximum=Decimal("400"))),
        "activityMultiplier": ("activity_multiplier", lambda v: _v1_decimal(v, minimum=Decimal("1"), maximum=Decimal("3"))),
        "dailyDeficit": ("daily_deficit_kcal", lambda v: int(v)),
        "dietType": ("diet_type", lambda v: str(v)[:30]),
        "workoutMode": ("workout_mode", lambda v: v if v in ("home", "gym") else "home"),
        "fitnessLevel": ("fitness_level", lambda v: v if v in ("beginner", "intermediate", "advanced") else "beginner"),
    }
    profile_updates = {}
    invalid_profile_fields = []
    for source, (target, convert) in metric_fields.items():
        if source not in raw:
            continue
        try:
            value = convert(raw[source])
        except (ValueError, TypeError, InvalidOperation):
            value = None
        if value is None:
            invalid_profile_fields.append(source)
        else:
            profile_updates[target] = value

    # Preserve the V1 meal-plan and workout-plan selections instead of resetting them.
    meal_index = _v1_int(raw.get("mealVariationIndex", 0), maximum=9999)
    workout_index = _v1_int(raw.get("workoutVariationIndex", 0), maximum=9999)
    if meal_index is not None:
        profile_updates["meal_variation_index"] = meal_index
    else:
        invalid_profile_fields.append("mealVariationIndex")
    if workout_index is not None:
        profile_updates["workout_variation_index"] = workout_index
    else:
        invalid_profile_fields.append("workoutVariationIndex")

    slot_offsets = raw.get("slotOffsets", {})
    if isinstance(slot_offsets, dict):
        clean_slots = {}
        for slot in ("Breakfast", "Lunch", "Snack", "Dinner"):
            offset = _v1_int(slot_offsets.get(slot, 0), maximum=9999)
            if offset is not None:
                clean_slots[slot] = offset
        profile_updates["slot_offsets"] = clean_slots
    elif "slotOffsets" in raw:
        invalid_profile_fields.append("slotOffsets")

    exercise_offsets = raw.get("exOffsets", {})
    if isinstance(exercise_offsets, dict):
        clean_exercise_offsets = {}
        for key, value in list(exercise_offsets.items())[:5]:
            index = _v1_int(key, maximum=4)
            offset = _v1_int(value, maximum=9999)
            if index is not None and offset is not None:
                clean_exercise_offsets[str(index)] = offset
        profile_updates["exercise_offsets"] = clean_exercise_offsets
    elif "exOffsets" in raw:
        invalid_profile_fields.append("exOffsets")

    completed_raw = raw.get("completedExercises", {})
    completed_exercises = {}
    if isinstance(completed_raw, dict):
        completed_exercises = {
            str(key)[:100]: value is True
            for key, value in list(completed_raw.items())[:500]
            if str(key).strip()
        }
        profile_updates["completed_exercises"] = completed_exercises
    elif "completedExercises" in raw:
        invalid_profile_fields.append("completedExercises")

    streak = _v1_int(raw.get("streakCount", 1), maximum=100000)
    if streak is not None:
        profile_updates["streak_count"] = max(1, streak)
    elif "streakCount" in raw:
        invalid_profile_fields.append("streakCount")

    if "lastActiveDate" in raw:
        try:
            profile_updates["last_active_date"] = datetime.strptime(
                str(raw["lastActiveDate"]), "%Y-%m-%d"
            ).date()
        except (TypeError, ValueError):
            invalid_profile_fields.append("lastActiveDate")

    fasting_raw = raw.get("fastingState")
    if fasting_raw is not None:
        if isinstance(fasting_raw, dict):
            protocol = _v1_int(fasting_raw.get("protocolHours", 16), minimum=1, maximum=24)
            elapsed = _v1_int(fasting_raw.get("elapsedMinutes", 0), maximum=1440)
            is_active = fasting_raw.get("isFasting", False)
            if protocol is None or elapsed is None or not isinstance(is_active, bool):
                invalid_profile_fields.append("fastingState")
            else:
                profile_updates["fasting_protocol_hours"] = protocol
                profile_updates["fasting_elapsed_minutes"] = elapsed
                profile_updates["fasting_is_active"] = is_active
        else:
            invalid_profile_fields.append("fastingState")

    selected_day = _v1_int(backup.get("selectedDayIndex", 0), maximum=6)
    if selected_day is not None:
        profile_updates["selected_day_index"] = selected_day

    favorite_raw = raw.get("favoriteMeals", {})
    favorite_names = []
    if isinstance(favorite_raw, dict):
        favorite_names = sorted({
            str(name).strip()[:180]
            for name, selected in list(favorite_raw.items())[:500]
            if selected is True and str(name).strip()
        })
    elif "favoriteMeals" in raw:
        invalid_profile_fields.append("favoriteMeals")

    matched_recipes = list(Recipe.objects.filter(name__in=favorite_names).only("id", "name"))
    matched_names = {recipe.name for recipe in matched_recipes}
    pending_favorite_names = [name for name in favorite_names if name not in matched_names]
    profile_updates["legacy_favorite_recipe_names"] = pending_favorite_names

    raw_set_logs = raw.get("hevySetLogs", {})
    if not isinstance(raw_set_logs, dict):
        raw_set_logs = {}
        invalid_profile_fields.append("hevySetLogs")
    if len(raw_set_logs) > 500:
        raise ValidationError({"backup": "The V1 workout set log exceeds the 500-exercise import limit."})

    clean_legacy_set_logs = {}
    workout_sets = []
    invalid_workout_sets = 0
    backup_unit = backup.get("unit", "metric")
    exercise_names = dict(
        Exercise.objects.filter(source_key__in=[str(key)[:100] for key in raw_set_logs])
        .values_list("source_key", "name")
    )

    for exercise_key_raw, set_rows in raw_set_logs.items():
        exercise_key = str(exercise_key_raw).strip()[:100]
        if not exercise_key or not isinstance(set_rows, list):
            invalid_workout_sets += 1
            continue
        if len(set_rows) > 50:
            invalid_workout_sets += len(set_rows) - 50
            set_rows = set_rows[:50]
        clean_rows = []
        used_set_numbers = set()
        for position, set_row in enumerate(set_rows, start=1):
            if not isinstance(set_row, dict):
                invalid_workout_sets += 1
                continue
            set_number = _v1_int(set_row.get("setNum", position), minimum=1, maximum=99)
            reps = _v1_int(set_row.get("reps"), maximum=2000) if set_row.get("reps") is not None else None
            weight = _v1_decimal(set_row.get("weight"), minimum=Decimal("0"), maximum=Decimal("10000"))
            if set_number is None or set_number in used_set_numbers:
                invalid_workout_sets += 1
                continue
            used_set_numbers.add(set_number)
            weight_kg = weight
            if weight_kg is not None and backup_unit == "imperial":
                weight_kg = (weight_kg / Decimal("2.20462")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            done = set_row.get("done") is True
            set_type = str(set_row.get("type", "working"))[:20]
            clean_row = {
                "set_number": set_number,
                "reps": reps,
                "weight_kg": weight_kg,
                "set_type": set_type or "working",
                "is_completed": done or completed_exercises.get(exercise_key, False),
            }
            clean_rows.append({
                "setNum": set_number,
                "reps": reps,
                "weight": weight_kg,
                "type": clean_row["set_type"],
                "done": clean_row["is_completed"],
            })
            workout_sets.append({
                "exercise_key": exercise_key,
                "exercise_name": exercise_names.get(exercise_key, exercise_key)[:180],
                **clean_row,
            })
        if clean_rows:
            clean_legacy_set_logs[exercise_key] = clean_rows

    # V1 checked exercise cards may exist even when no detailed Hevy set array was saved.
    for exercise_key, is_done in completed_exercises.items():
        if is_done and exercise_key not in clean_legacy_set_logs:
            exercise_name = exercise_names.get(exercise_key, exercise_key)[:180]
            workout_sets.append({
                "exercise_key": exercise_key,
                "exercise_name": exercise_name,
                "set_number": 1,
                "reps": None,
                "weight_kg": None,
                "set_type": "legacy-completed",
                "is_completed": True,
            })

    has_completed_workout = any(row["is_completed"] for row in workout_sets)
    if not has_completed_workout:
        workout_sets = []

    profile_updates["legacy_workout_state"] = {
        "hevySetLogs": clean_legacy_set_logs,
        "completedExercises": completed_exercises,
    }

    unit = backup.get("unit")
    if unit in ("metric", "imperial"):
        profile_updates["unit_system"] = unit

    supported = {
        "name", "age", "gender", "heightCm", "startWeightKg", "currentWeightKg",
        "goalWeightKg", "activityMultiplier", "dailyDeficit", "dietType",
        "workoutMode", "fitnessLevel", "waterGlasses", "foodDiary", "weightLogs",
        "mealVariationIndex", "slotOffsets", "workoutVariationIndex", "exOffsets",
        "completedExercises", "streakCount", "lastActiveDate", "fastingState",
        "favoriteMeals", "hevySetLogs",
    }
    unsupported = sorted(
        key for key, value in raw.items()
        if key not in supported and value not in (None, "", [], {})
    )
    fingerprint_source = json.dumps(
        {"profile_id": profile_id, "profile": raw, "unit": unit},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    fingerprint = hashlib.sha256(fingerprint_source).hexdigest()
    duplicate = DataImportBatch.objects.filter(actor=request.user, fingerprint=fingerprint).exists()

    existing_favorite_ids = set(
        RecipeFavorite.objects.filter(
            user=request.user,
            recipe_id__in=[recipe.pk for recipe in matched_recipes],
        ).values_list("recipe_id", flat=True)
    )
    new_favorite_ids = [recipe.pk for recipe in matched_recipes if recipe.pk not in existing_favorite_ids]

    return {
        "profile_id": profile_id,
        "fingerprint": fingerprint,
        "profile_updates": profile_updates,
        "weights": weights,
        "measurements": measurements,
        "foods": foods,
        "water_ml": glasses * 250,
        "workout_sets": workout_sets,
        "favorite_recipe_ids": new_favorite_ids,
        "pending_favorite_names": pending_favorite_names,
        "invalid_workout_sets": invalid_workout_sets,
        "invalid_weights": invalid_weights,
        "invalid_foods": invalid_foods,
        "invalid_profile_fields": invalid_profile_fields,
        "unsupported_fields": unsupported,
        "duplicate": duplicate,
        "counts": {
            "weight_entries": len(weights),
            "body_measurements": len(measurements),
            "food_entries": len(foods),
            "water_glasses": glasses,
            "water_ml_estimate": glasses * 250,
            "workout_sessions": 1 if workout_sets else 0,
            "workout_sets": len(workout_sets),
            "recipe_favorites": len(new_favorite_ids),
            "unmatched_favorite_names": len(pending_favorite_names),
        },
    }

class V1ImportPreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        plan = _v1_import_plan(
            request,
            backup=request.data.get("backup"),
            profile_id=request.data.get("profile_id"),
        )
        return Response({
            "source_profile": plan["profile_id"],
            "counts": plan["counts"],
            "profile_fields_to_update": sorted(plan["profile_updates"].keys()),
            "invalid_entries_skipped": {
                "weight_logs": plan["invalid_weights"],
                "food_diary": plan["invalid_foods"],
                "profile_fields": plan["invalid_profile_fields"],
            },
            "unsupported_fields": plan["unsupported_fields"],
            "already_imported": plan["duplicate"],
            "warnings": [
                "V1 food diary entries have no timestamps; they will be assigned the import time.",
                "V1 waterGlasses is a current-day counter, not a dated history. The importer converts it to one estimated total using 250 ml per glass.",
                "Only the selected person's profile is imported. The other partner's data is not copied to this account.",
                "Existing V2 logs are preserved; imported entries are appended. Profile settings listed above will be updated.",
            ],
        })


class V1ImportCommitView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.data.get("confirm") is not True:
            raise ValidationError({"confirm": "Review the preview, then send confirm=true to import."})
        with transaction.atomic():
            plan = _v1_import_plan(
                request,
                backup=request.data.get("backup"),
                profile_id=request.data.get("profile_id"),
            )
            if plan["duplicate"]:
                return Response({"detail": "This exact V1 profile backup has already been imported into this account."}, status=409)

            profile, _ = PersonalProfile.objects.get_or_create(user=request.user)
            for field, value in plan["profile_updates"].items():
                setattr(profile, field, value)
            try:
                profile.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(getattr(exc, "message_dict", exc.messages)) from exc
            profile.save()

            WeightEntry.objects.bulk_create([
                WeightEntry(owner=request.user, **entry) for entry in plan["weights"]
            ])
            BodyMeasurement.objects.bulk_create([
                BodyMeasurement(owner=request.user, **entry) for entry in plan["measurements"]
            ])
            import_time = timezone.now()
            FoodEntry.objects.bulk_create([
                FoodEntry(
                    owner=request.user,
                    logged_at=import_time,
                    meal_slot=FoodEntry.MealSlot.OTHER,
                    quantity=1,
                    **entry,
                )
                for entry in plan["foods"]
            ])
            if plan["water_ml"] > 0:
                WaterEntry.objects.create(owner=request.user, amount_ml=plan["water_ml"], logged_at=import_time)

            batch = DataImportBatch.objects.create(
                actor=request.user,
                source_profile=plan["profile_id"],
                fingerprint=plan["fingerprint"],
                counts=plan["counts"],
            )
            AuditEvent.objects.create(
                actor=request.user,
                event_type="data.v1_import.completed",
                target_type="v1_import",
                target_id=str(batch.pk),
                metadata={"source_profile": plan["profile_id"], **plan["counts"]},
            )

        return Response({
            "detail": "V1 profile imported.",
            "source_profile": plan["profile_id"],
            "counts": plan["counts"],
            "unsupported_fields": plan["unsupported_fields"],
            "invalid_entries_skipped": {
                "weight_logs": plan["invalid_weights"],
                "food_diary": plan["invalid_foods"],
                "profile_fields": plan["invalid_profile_fields"],
            },
        }, status=201)


class RecipeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RecipeSerializer
    queryset = Recipe.objects.all()

    def get_queryset(self):
        queryset = Recipe.objects.all()
        diet_style = self.request.query_params.get("diet_style")
        slot = self.request.query_params.get("slot")
        search = self.request.query_params.get("search")
        if diet_style:
            queryset = queryset.filter(diet_style=diet_style)
        if slot:
            queryset = queryset.filter(slot__iexact=slot)
        if search:
            queryset = queryset.filter(name__icontains=search[:120])
        return queryset


class ExerciseViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExerciseSerializer
    queryset = Exercise.objects.all()

    def get_queryset(self):
        queryset = Exercise.objects.all()
        search = self.request.query_params.get("search")
        focus = self.request.query_params.get("focus")
        if search:
            queryset = queryset.filter(name__icontains=search[:120])
        if focus:
            queryset = queryset.filter(focus__icontains=focus[:120])
        return queryset


class WorkoutRoutineViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkoutRoutineSerializer
    queryset = WorkoutRoutine.objects.all()

    def get_queryset(self):
        queryset = WorkoutRoutine.objects.prefetch_related("exercise_links__exercise")
        mode = self.request.query_params.get("mode")
        level = self.request.query_params.get("level")
        if mode:
            queryset = queryset.filter(mode=mode)
        if level:
            queryset = queryset.filter(level=level)
        return queryset


class RecipeFavoritesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        favorites = RecipeFavorite.objects.filter(user=request.user).select_related("recipe")
        return Response(RecipeFavoriteSerializer(favorites, many=True, context={"request": request}).data)

    def post(self, request):
        recipe_id = request.data.get("recipe_id")
        if isinstance(recipe_id, bool):
            raise ValidationError({"recipe_id": "A recipe ID is required."})
        try:
            recipe_id = int(recipe_id)
        except (TypeError, ValueError):
            raise ValidationError({"recipe_id": "A valid recipe ID is required."})
        recipe = get_object_or_404(Recipe, pk=recipe_id)
        favorite, created = RecipeFavorite.objects.get_or_create(user=request.user, recipe=recipe)
        return Response(
            RecipeFavoriteSerializer(favorite, context={"request": request}).data,
            status=201 if created else 200,
        )


class RecipeFavoriteDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, recipe_id: int):
        favorite = get_object_or_404(RecipeFavorite, user=request.user, recipe_id=recipe_id)
        favorite.delete()
        return Response(status=204)
