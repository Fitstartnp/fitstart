from copy import copy

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.households.models import Household, HouseholdMembership
from apps.catalog.models import Exercise, Recipe, RecipeFavorite, RoutineExercise, WorkoutRoutine
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
)


class PersonalRecordSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    household = serializers.PrimaryKeyRelatedField(
        queryset=Household.objects.none(),
        required=False,
        allow_null=True,
    )

    class Meta:
        fields = "__all__"
        read_only_fields = ("id", "owner", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and "household" in self.fields:
            self.fields["household"].queryset = Household.objects.filter(
                archived_at__isnull=True,
                memberships__user=request.user,
                memberships__status=HouseholdMembership.Status.ACTIVE,
            ).distinct()

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication is required.")

        candidate = copy(self.instance) if self.instance is not None else self.Meta.model(owner=request.user)
        for field, value in attrs.items():
            setattr(candidate, field, value)

        household = getattr(candidate, "household", None)
        if household is not None:
            preference = getattr(self.Meta.model, "sharing_preference", None)
            if not preference:
                raise serializers.ValidationError({"household": "This record type cannot be shared."})
            is_enabled = PersonalProfile.objects.filter(
                user=request.user,
                **{preference: True},
            ).exists()
            if not is_enabled:
                raise serializers.ValidationError(
                    {"household": "Enable sharing for this category in your profile before sharing this record."}
                )
            is_member = HouseholdMembership.objects.filter(
                household=household,
                user=request.user,
                status=HouseholdMembership.Status.ACTIVE,
            ).exists()
            if not is_member:
                raise serializers.ValidationError({"household": "You must be an active member of this household."})

        try:
            candidate.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(getattr(exc, "message_dict", exc.messages)) from exc
        return attrs


class WeightEntrySerializer(PersonalRecordSerializer):
    class Meta(PersonalRecordSerializer.Meta):
        model = WeightEntry
        fields = "__all__"


class BodyMeasurementSerializer(PersonalRecordSerializer):
    class Meta(PersonalRecordSerializer.Meta):
        model = BodyMeasurement
        fields = "__all__"


class FoodEntrySerializer(PersonalRecordSerializer):
    class Meta(PersonalRecordSerializer.Meta):
        model = FoodEntry
        fields = "__all__"


class WaterEntrySerializer(PersonalRecordSerializer):
    class Meta(PersonalRecordSerializer.Meta):
        model = WaterEntry
        fields = "__all__"


class MealPlanEntrySerializer(PersonalRecordSerializer):
    class Meta(PersonalRecordSerializer.Meta):
        model = MealPlanEntry
        fields = "__all__"


class GroceryListSerializer(PersonalRecordSerializer):
    class Meta(PersonalRecordSerializer.Meta):
        model = GroceryList
        fields = "__all__"


class WorkoutSessionSerializer(PersonalRecordSerializer):
    class Meta(PersonalRecordSerializer.Meta):
        model = WorkoutSession
        fields = "__all__"


class FastingSessionSerializer(PersonalRecordSerializer):
    class Meta(PersonalRecordSerializer.Meta):
        model = FastingSession
        fields = "__all__"


class GoalSerializer(PersonalRecordSerializer):
    class Meta(PersonalRecordSerializer.Meta):
        model = Goal
        fields = "__all__"



class GroceryItemSerializer(serializers.ModelSerializer):
    grocery_list = serializers.PrimaryKeyRelatedField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        from apps.tracking.models import GroceryItem
        model = GroceryItem
        fields = "__all__"
        read_only_fields = ("id", "grocery_list", "created_at")


class WorkoutSetSerializer(serializers.ModelSerializer):
    session = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        from apps.tracking.models import WorkoutSet
        model = WorkoutSet
        fields = "__all__"
        read_only_fields = ("id", "session")


class RecipeSerializer(serializers.ModelSerializer):
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = "__all__"
        read_only_fields = fields

    def get_is_favorite(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return RecipeFavorite.objects.filter(user=request.user, recipe=obj).exists()


class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = "__all__"
        read_only_fields = fields


class RoutineExerciseSerializer(serializers.ModelSerializer):
    exercise = ExerciseSerializer(read_only=True)

    class Meta:
        model = RoutineExercise
        fields = ("id", "position", "exercise")
        read_only_fields = fields


class WorkoutRoutineSerializer(serializers.ModelSerializer):
    exercise_links = RoutineExerciseSerializer(many=True, read_only=True)

    class Meta:
        model = WorkoutRoutine
        fields = ("id", "mode", "level", "variation_index", "title", "exercise_links")
        read_only_fields = fields


class RecipeFavoriteSerializer(serializers.ModelSerializer):
    recipe = RecipeSerializer(read_only=True)

    class Meta:
        model = RecipeFavorite
        fields = ("id", "recipe", "created_at")
        read_only_fields = fields
