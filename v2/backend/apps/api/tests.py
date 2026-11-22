from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import User
from apps.catalog.models import Recipe, RecipeFavorite
from apps.households.models import HouseholdInvitation, HouseholdMembership
from apps.households.services import create_household, create_invitation


class ApiAccessTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice@example.com", "long-alice-password")
        self.bob = User.objects.create_user("bob@example.com", "long-bob-password")
        self.alice_household = create_household(owner=self.alice, name="Alice household")
        self.bob_household = create_household(owner=self.bob, name="Bob household")

    def test_me_requires_an_authenticated_session(self):
        response = self.client.get("/api/v1/me/")
        self.assertIn(response.status_code, (401, 403))

    def test_me_returns_only_the_current_account(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get("/api/v1/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "alice@example.com")
        self.assertNotIn("bob@example.com", str(response.data))

    def test_household_list_is_scoped_to_the_current_user(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get("/api/v1/households/")
        self.assertEqual(response.status_code, 200)
        names = [row["name"] for row in response.data]
        self.assertEqual(names, ["Alice household"])
        self.assertNotIn("Bob household", names)

    def test_health_endpoint_does_not_require_a_session(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ok"})


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FITSTART_PUBLIC_URL="https://fitstart.example.test",
)
class HouseholdInvitationApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@example.com", "long-owner-password")
        self.member = User.objects.create_user("member@example.com", "long-member-password")
        self.household = create_household(owner=self.owner, name="FitStart Home")

    def test_owner_invite_sends_link_without_returning_raw_token(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            f"/api/v1/households/{self.household.pk}/invitations/",
            {"email": "invitee@example.com", "role": "member"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("token", str(response.data).lower())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://fitstart.example.test/invite/#", mail.outbox[0].body)
        raw_token = mail.outbox[0].body.split("#", 1)[1].split()[0]
        invitation = HouseholdInvitation.objects.get(invited_email="invitee@example.com")
        self.assertTrue(invitation.matches_token(raw_token))
        self.assertNotIn(raw_token, invitation.token_digest)

    def test_household_member_cannot_send_invites(self):
        HouseholdMembership.objects.create(
            household=self.household,
            user=self.member,
            role=HouseholdMembership.Role.MEMBER,
        )
        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            f"/api/v1/households/{self.household.pk}/invitations/",
            {"email": "another@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_unregistered_invited_email_can_create_account_and_accept(self):
        invitation, raw_token = create_invitation(
            actor=self.owner,
            household=self.household,
            email="newperson@example.com",
        )
        client = APIClient(enforce_csrf_checks=True)
        no_csrf = client.post(
            "/api/v1/invitations/accept/",
            {"token": raw_token, "password": "Secure-password-2026!"},
            format="json",
        )
        self.assertEqual(no_csrf.status_code, 403)

        page = client.get("/invite/")
        self.assertEqual(page.status_code, 200)
        csrf = client.cookies["csrftoken"].value
        response = client.post(
            "/api/v1/invitations/accept/",
            {"token": raw_token, "password": "Secure-password-2026!"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn(raw_token, str(response.data))
        new_user = User.objects.get(email="newperson@example.com")
        self.assertIsNotNone(new_user.email_verified_at)
        self.assertTrue(new_user.check_password("Secure-password-2026!"))
        self.assertTrue(
            HouseholdMembership.objects.filter(
                user=new_user,
                household=self.household,
                role=HouseholdMembership.Role.MEMBER,
                status=HouseholdMembership.Status.ACTIVE,
            ).exists()
        )
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)
        self.assertTrue(client.session.get("_auth_user_id"))

        replay = client.post(
            "/api/v1/invitations/accept/",
            {"token": raw_token},
            format="json",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(replay.status_code, 400)

    def test_existing_account_must_sign_in_before_accepting(self):
        invitation, raw_token = create_invitation(
            actor=self.owner,
            household=self.household,
            email=self.member.email,
        )
        response = self.client.post(
            "/api/v1/invitations/accept/",
            {"token": raw_token, "password": "unused-long-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        invitation.refresh_from_db()
        self.assertIsNone(invitation.accepted_at)

    def test_logged_in_wrong_account_cannot_accept_invitation(self):
        invitation, raw_token = create_invitation(
            actor=self.owner,
            household=self.household,
            email="different@example.com",
        )
        self.member.email_verified_at = timezone.now()
        self.member.save(update_fields=("email_verified_at",))
        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            "/api/v1/invitations/accept/",
            {"token": raw_token},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        invitation.refresh_from_db()
        self.assertIsNone(invitation.accepted_at)


class PersonalRecordApiTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user("record-owner@example.com", "long-alice-password")
        self.bob = User.objects.create_user("record-member@example.com", "long-bob-password")
        self.household = create_household(owner=self.alice, name="Shared home")
        from apps.households.models import HouseholdMembership
        HouseholdMembership.objects.create(
            household=self.household,
            user=self.bob,
            role=HouseholdMembership.Role.MEMBER,
            status=HouseholdMembership.Status.ACTIVE,
        )

    def test_weight_entry_requires_authentication(self):
        response = self.client.get("/api/v1/weight-entries/")
        self.assertIn(response.status_code, (401, 403))

    def test_owner_can_create_and_list_private_weight_entry(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(
            "/api/v1/weight-entries/",
            {"weight_kg": "81.50", "note": "Morning"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["owner"], self.alice.pk)
        self.assertIsNone(response.data["household"])
        self.alice.refresh_from_db()
        self.assertEqual(str(self.alice.personal_profile.current_weight_kg), "81.50")
        listing = self.client.get("/api/v1/weight-entries/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data), 1)

    def test_private_weight_entry_is_not_visible_to_another_user(self):
        self.client.force_authenticate(user=self.alice)
        created = self.client.post(
            "/api/v1/weight-entries/",
            {"weight_kg": "81.50"},
            format="json",
        )
        entry_id = created.data["id"]
        self.client.force_authenticate(user=self.bob)
        listing = self.client.get("/api/v1/weight-entries/")
        self.assertEqual(listing.data, [])
        detail = self.client.get(f"/api/v1/weight-entries/{entry_id}/")
        self.assertEqual(detail.status_code, 404)

    def test_shared_weight_is_visible_but_not_editable_by_household_member(self):
        self.client.force_authenticate(user=self.alice)
        profile = self.client.patch(
            "/api/v1/profile/",
            {"share_weight_history": True},
            format="json",
        )
        self.assertEqual(profile.status_code, 200, profile.data)
        created = self.client.post(
            "/api/v1/weight-entries/",
            {"weight_kg": "80.25", "household": self.household.pk},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        entry_id = created.data["id"]

        self.client.force_authenticate(user=self.bob)
        listing = self.client.get("/api/v1/weight-entries/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([item["id"] for item in listing.data], [entry_id])
        detail = self.client.get(f"/api/v1/weight-entries/{entry_id}/")
        self.assertEqual(detail.status_code, 200)
        update = self.client.patch(
            f"/api/v1/weight-entries/{entry_id}/",
            {"weight_kg": "70.00"},
            format="json",
        )
        self.assertEqual(update.status_code, 404)

    def test_sharing_preference_is_required_before_assigning_household(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(
            "/api/v1/weight-entries/",
            {"weight_kg": "80.25", "household": self.household.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("household", response.data)

    def test_share_toggle_does_not_expose_food_diary(self):
        self.client.force_authenticate(user=self.alice)
        self.client.patch(
            "/api/v1/profile/",
            {"share_weight_history": True},
            format="json",
        )
        created = self.client.post(
            "/api/v1/food-entries/",
            {"food_name": "Private lunch", "calories_kcal": "550"},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.client.force_authenticate(user=self.bob)
        listing = self.client.get("/api/v1/food-entries/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data, [])

    def test_profile_api_changes_only_the_current_users_preferences(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.patch(
            "/api/v1/profile/",
            {"display_name": "Alice", "unit_system": "imperial"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["display_name"], "Alice")
        self.client.force_authenticate(user=self.bob)
        own = self.client.get("/api/v1/profile/")
        self.assertEqual(own.data["display_name"], "")
        self.assertEqual(own.data["unit_system"], "metric")


class NestedChildRecordApiTests(APITestCase):
    def setUp(self):
        from apps.households.models import HouseholdMembership
        from apps.tracking.models import GroceryList, WorkoutSession

        self.owner = User.objects.create_user("nested-owner@example.com", "long-owner-password")
        self.member = User.objects.create_user("nested-member@example.com", "long-member-password")
        self.household = create_household(owner=self.owner, name="Nested records home")
        HouseholdMembership.objects.create(
            household=self.household,
            user=self.member,
            role=HouseholdMembership.Role.MEMBER,
            status=HouseholdMembership.Status.ACTIVE,
        )
        profile = self.owner.personal_profile
        profile.share_grocery_lists = True
        profile.share_workout_history = True
        profile.save(update_fields=("share_grocery_lists", "share_workout_history", "updated_at"))

        self.grocery_list = GroceryList(
            owner=self.owner,
            household=self.household,
            name="Shared weekly groceries",
        )
        self.grocery_list.full_clean()
        self.grocery_list.save()

        self.workout = WorkoutSession(
            owner=self.owner,
            household=self.household,
            title="Strength session",
        )
        self.workout.full_clean()
        self.workout.save()

    def test_grocery_items_inherit_parent_sharing_but_only_owner_can_change(self):
        self.client.force_authenticate(user=self.owner)
        created = self.client.post(
            f"/api/v1/grocery-lists/{self.grocery_list.pk}/items/",
            {"name": "Oats", "quantity": "1 bag", "category": "Pantry"},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        item_id = created.data["id"]

        self.client.force_authenticate(user=self.member)
        listing = self.client.get(f"/api/v1/grocery-lists/{self.grocery_list.pk}/items/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([item["name"] for item in listing.data], ["Oats"])
        denied = self.client.post(
            f"/api/v1/grocery-lists/{self.grocery_list.pk}/items/",
            {"name": "Milk"},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)
        patch = self.client.patch(
            f"/api/v1/grocery-lists/{self.grocery_list.pk}/items/{item_id}/",
            {"is_checked": True},
            format="json",
        )
        self.assertEqual(patch.status_code, 404)

    def test_workout_sets_inherit_parent_sharing_but_only_owner_can_change(self):
        self.client.force_authenticate(user=self.owner)
        created = self.client.post(
            f"/api/v1/workout-sessions/{self.workout.pk}/sets/",
            {
                "exercise_key": "squat",
                "exercise_name": "Squat",
                "set_number": 1,
                "reps": 10,
                "weight_kg": "40.00",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        set_id = created.data["id"]

        self.client.force_authenticate(user=self.member)
        listing = self.client.get(f"/api/v1/workout-sessions/{self.workout.pk}/sets/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([item["exercise_name"] for item in listing.data], ["Squat"])
        denied = self.client.post(
            f"/api/v1/workout-sessions/{self.workout.pk}/sets/",
            {"exercise_key": "press", "exercise_name": "Press", "set_number": 1, "reps": 8},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)
        patch = self.client.patch(
            f"/api/v1/workout-sessions/{self.workout.pk}/sets/{set_id}/",
            {"reps": 12},
            format="json",
        )
        self.assertEqual(patch.status_code, 404)


class TimedSessionPermissionsTests(APITestCase):
    def setUp(self):
        from apps.households.models import HouseholdMembership
        from apps.tracking.models import WorkoutSession
        from django.utils import timezone

        self.owner = User.objects.create_user("timed-owner@example.com", "long-owner-password")
        self.member = User.objects.create_user("timed-member@example.com", "long-member-password")
        self.household = create_household(owner=self.owner, name="Timed session home")
        HouseholdMembership.objects.create(
            household=self.household,
            user=self.member,
            role=HouseholdMembership.Role.MEMBER,
            status=HouseholdMembership.Status.ACTIVE,
        )
        profile = self.owner.personal_profile
        profile.share_workout_history = True
        profile.share_fasting_sessions = True
        profile.save(update_fields=("share_workout_history", "share_fasting_sessions", "updated_at"))
        self.workout = WorkoutSession(
            owner=self.owner,
            household=self.household,
            title="Shared workout",
            started_at=timezone.now(),
        )
        self.workout.full_clean()
        self.workout.save()

    def test_only_owner_can_finish_shared_workout(self):
        from django.utils import timezone

        self.client.force_authenticate(user=self.member)
        denied = self.client.patch(
            f"/api/v1/workout-sessions/{self.workout.pk}/",
            {"ended_at": timezone.now().isoformat()},
            format="json",
        )
        self.assertEqual(denied.status_code, 404)

        self.client.force_authenticate(user=self.owner)
        finished = self.client.patch(
            f"/api/v1/workout-sessions/{self.workout.pk}/",
            {"ended_at": (timezone.now() + timezone.timedelta(minutes=1)).isoformat()},
            format="json",
        )
        self.assertEqual(finished.status_code, 200, finished.data)
        self.assertIsNotNone(finished.data["ended_at"])


class PersonalProfileMetricsApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("metrics@example.com", "long-metrics-password")

    def test_user_can_read_and_update_body_goal_and_activity_settings(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            "/api/v1/profile/",
            {
                "age": 34,
                "gender": "female",
                "height_cm": "167.50",
                "start_weight_kg": "78.00",
                "current_weight_kg": "74.25",
                "goal_weight_kg": "65.00",
                "activity_multiplier": "1.55",
                "daily_deficit_kcal": 350,
                "diet_type": "mediterranean",
                "workout_mode": "gym",
                "fitness_level": "intermediate",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["age"], 34)
        self.assertEqual(response.data["gender"], "female")
        self.assertEqual(str(response.data["height_cm"]), "167.50")
        self.assertEqual(str(response.data["current_weight_kg"]), "74.25")
        self.assertEqual(response.data["workout_mode"], "gym")
        self.assertEqual(response.data["fitness_level"], "intermediate")

    def test_invalid_age_or_gender_is_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            "/api/v1/profile/",
            {"age": 140, "gender": "unknown"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class V1BackupImportApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("v1-import@example.com", "long-import-password")
        self.recipe = Recipe.objects.create(
            diet_style="balanced",
            menu_number=1,
            slot_position=1,
            slot="Breakfast",
            ratio="1.00",
            base_calories_kcal=450,
            name="Oats",
            portions=[],
            base_macros={},
            steps=[],
        )
        self.backup = {
            "unit": "metric",
            "activeProfileId": "husband",
            "profiles": {
                "husband": {
                    "name": "Alex",
                    "age": 35,
                    "gender": "male",
                    "heightCm": 180,
                    "startWeightKg": 100,
                    "currentWeightKg": 95,
                    "goalWeightKg": 85,
                    "activityMultiplier": 1.55,
                    "dailyDeficit": 400,
                    "dietType": "balanced",
                    "workoutMode": "gym",
                    "fitnessLevel": "intermediate",
                    "mealVariationIndex": 2,
                    "slotOffsets": {"Breakfast": 1, "Lunch": 2, "Snack": 0, "Dinner": 3},
                    "workoutVariationIndex": 1,
                    "exOffsets": {"0": 1, "1": 2},
                    "streakCount": 5,
                    "lastActiveDate": "2026-02-01",
                    "fastingState": {"protocolHours": 16, "isFasting": True, "elapsedMinutes": 540},
                    "favoriteMeals": {"Oats": True},
                    "hevySetLogs": {
                        "squat": [
                            {"setNum": 1, "type": "W", "weight": 60, "reps": 8, "done": True},
                            {"setNum": 2, "type": "1", "weight": 65, "reps": 6, "done": False},
                        ]
                    },
                    "waterGlasses": 4,
                    "weightLogs": [
                        {"date": "2026-01-01", "weightKg": 100, "waistCm": 100, "note": "Start"},
                        {"date": "2026-02-01", "weightKg": 95, "waistCm": 96, "note": "Latest"},
                    ],
                    "foodDiary": [
                        {"name": "Oats", "kcal": 450, "p": 20, "c": 60, "f": 10, "fib": 8},
                    ],
                    "completedExercises": {"squat": True, "plank": False},
                },
                "wife": {
                    "name": "Partner",
                    "age": 29,
                    "gender": "female",
                    "heightCm": 165,
                    "startWeightKg": 72,
                    "currentWeightKg": 70,
                    "goalWeightKg": 62,
                    "waterGlasses": 2,
                    "weightLogs": [
                        {"date": "2026-01-01", "weightKg": 72, "waistCm": 80, "note": "Partner start"},
                    ],
                    "foodDiary": [
                        {"name": "Yogurt", "kcal": 160, "p": 12, "c": 15, "f": 5, "fib": 1},
                    ],
                },
            },
            # This is deliberately not imported or persisted.
            "cloudConfig": {"token": "DO_NOT_IMPORT_THIS_TOKEN"},
        }

    def test_preview_only_reports_selected_profile_and_does_not_write(self):
        from apps.tracking.models import FoodEntry, WeightEntry

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/imports/v1/preview/",
            {"backup": self.backup, "profile_id": "husband"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["source_profile"], "husband")
        self.assertEqual(response.data["counts"]["weight_entries"], 2)
        self.assertEqual(response.data["counts"]["food_entries"], 1)
        self.assertEqual(response.data["counts"]["water_glasses"], 4)
        self.assertNotIn("completedExercises", response.data["unsupported_fields"])
        self.assertEqual(response.data["counts"]["workout_sets"], 2)
        self.assertEqual(response.data["counts"]["workout_sessions"], 1)
        self.assertEqual(response.data["counts"]["recipe_favorites"], 1)
        self.assertFalse(response.data["already_imported"])
        self.assertEqual(WeightEntry.objects.filter(owner=self.user).count(), 0)
        self.assertEqual(FoodEntry.objects.filter(owner=self.user).count(), 0)

    def test_commit_imports_only_selected_profile_and_is_idempotent(self):
        from apps.audit.models import DataImportBatch
        from apps.profiles.models import PersonalProfile
        from apps.tracking.models import BodyMeasurement, FoodEntry, WaterEntry, WeightEntry, WorkoutSession, WorkoutSet

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/imports/v1/commit/",
            {"backup": self.backup, "profile_id": "husband", "confirm": True},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["source_profile"], "husband")
        self.assertEqual(WeightEntry.objects.filter(owner=self.user).count(), 2)
        self.assertEqual(FoodEntry.objects.filter(owner=self.user).count(), 1)
        self.assertEqual(BodyMeasurement.objects.filter(owner=self.user).count(), 2)
        self.assertEqual(WaterEntry.objects.get(owner=self.user).amount_ml, 1000)
        self.assertEqual(WorkoutSession.objects.filter(owner=self.user).count(), 1)
        self.assertEqual(WorkoutSet.objects.filter(session__owner=self.user).count(), 2)
        self.assertEqual(
            WorkoutSet.objects.filter(session__owner=self.user, is_completed=True).count(),
            2,
        )
        self.assertTrue(
            RecipeFavorite.objects.filter(user=self.user, recipe=self.recipe).exists()
        )

        profile = PersonalProfile.objects.get(user=self.user)
        self.assertEqual(profile.display_name, "Alex")
        self.assertEqual(profile.age, 35)
        self.assertEqual(profile.height_cm, 180)
        self.assertEqual(profile.goal_weight_kg, 85)
        self.assertEqual(profile.workout_mode, "gym")
        self.assertEqual(profile.meal_variation_index, 2)
        self.assertEqual(profile.slot_offsets["Breakfast"], 1)
        self.assertEqual(profile.workout_variation_index, 1)
        self.assertEqual(profile.exercise_offsets["0"], 1)
        self.assertEqual(profile.streak_count, 5)
        self.assertEqual(str(profile.last_active_date), "2026-02-01")
        self.assertEqual(profile.fasting_protocol_hours, 16)
        self.assertTrue(profile.fasting_is_active)
        self.assertEqual(profile.fasting_elapsed_minutes, 540)
        self.assertTrue(profile.completed_exercises["squat"])
        self.assertEqual(len(profile.legacy_workout_state.get("hevySetLogs", {}).get("squat", [])), 2)

        self.assertEqual(DataImportBatch.objects.filter(actor=self.user).count(), 1)
        self.assertNotIn(
            "DO_NOT_IMPORT_THIS_TOKEN",
            str(list(DataImportBatch.objects.filter(actor=self.user).values())),
        )

        duplicate = self.client.post(
            "/api/v1/imports/v1/commit/",
            {"backup": self.backup, "profile_id": "husband", "confirm": True},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(WeightEntry.objects.filter(owner=self.user).count(), 2)

    def test_other_partner_profile_can_be_imported_separately_without_mixing(self):
        from apps.profiles.models import PersonalProfile
        from apps.tracking.models import FoodEntry, WeightEntry

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/imports/v1/commit/",
            {"backup": self.backup, "profile_id": "wife", "confirm": True},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        profile = PersonalProfile.objects.get(user=self.user)
        self.assertEqual(profile.display_name, "Partner")
        self.assertEqual(profile.gender, "female")
        self.assertEqual(list(WeightEntry.objects.filter(owner=self.user).values_list("weight_kg", flat=True)), [72])
        self.assertEqual(FoodEntry.objects.get(owner=self.user).food_name, "Yogurt")

    def test_commit_requires_confirmation_and_valid_profile_choice(self):
        self.client.force_authenticate(user=self.user)
        no_confirm = self.client.post(
            "/api/v1/imports/v1/commit/",
            {"backup": self.backup, "profile_id": "husband"},
            format="json",
        )
        self.assertEqual(no_confirm.status_code, 400)
        invalid_profile = self.client.post(
            "/api/v1/imports/v1/preview/",
            {"backup": self.backup, "profile_id": "both"},
            format="json",
        )
        self.assertEqual(invalid_profile.status_code, 400)


class MyDataExportApiTests(APITestCase):
    def setUp(self):
        from apps.households.models import HouseholdMembership
        from apps.households.services import create_household
        from apps.profiles.models import PersonalProfile
        from apps.tracking.models import (
            FoodEntry, GroceryItem, GroceryList, WeightEntry, WorkoutSession, WorkoutSet,
        )

        self.alice = User.objects.create_user("export-alice@example.com", "long-alice-password")
        self.bob = User.objects.create_user("export-bob@example.com", "long-bob-password")
        self.household = create_household(owner=self.alice, name="Export household")
        HouseholdMembership.objects.create(
            household=self.household,
            user=self.bob,
            role=HouseholdMembership.Role.MEMBER,
            status=HouseholdMembership.Status.ACTIVE,
        )
        alice_profile = PersonalProfile.objects.get(user=self.alice)
        alice_profile.share_weight_history = True
        alice_profile.save(update_fields=("share_weight_history", "updated_at"))

        WeightEntry.objects.create(owner=self.alice, household=self.household, weight_kg="90.00")
        self.bob_weight = WeightEntry.objects.create(owner=self.bob, weight_kg="75.00")
        FoodEntry.objects.create(owner=self.bob, food_name="Private breakfast", calories_kcal="350")
        grocery = GroceryList.objects.create(owner=self.bob, name="My private list")
        GroceryItem.objects.create(grocery_list=grocery, name="Apples", quantity="4")
        workout = WorkoutSession.objects.create(owner=self.bob, title="My workout")
        WorkoutSet.objects.create(
            session=workout,
            exercise_key="squat",
            exercise_name="Squat",
            set_number=1,
            reps=10,
            weight_kg="40.00",
        )

    def test_export_requires_authentication(self):
        response = self.client.get("/api/v1/export/")
        self.assertIn(response.status_code, (401, 403))

    def test_export_contains_only_current_accounts_owned_records_and_nested_data(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get("/api/v1/export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response.data["format"], "fitstart-v2-export")
        self.assertEqual(
            [row["id"] for row in response.data["records"]["weight_entries"]],
            [self.bob_weight.pk],
        )
        self.assertNotIn(
            "90.00",
            str(response.data["records"]["weight_entries"]),
        )
        self.assertEqual(
            response.data["records"]["food_entries"][0]["food_name"],
            "Private breakfast",
        )
        self.assertEqual(
            response.data["records"]["grocery_lists"][0]["items"][0]["name"],
            "Apples",
        )
        self.assertEqual(
            response.data["records"]["workout_sessions"][0]["sets"][0]["exercise_name"],
            "Squat",
        )
        serialized = str(response.data)
        self.assertNotIn("password", serialized.lower())
        self.assertNotIn("cloudConfig", serialized)
        self.assertNotIn("gist_token", serialized.lower())


class MyDataExportApiTests(APITestCase):
    def setUp(self):
        from apps.households.models import HouseholdMembership
        from apps.households.services import create_household
        from apps.profiles.models import PersonalProfile
        from apps.tracking.models import (
            FoodEntry, GroceryItem, GroceryList, WeightEntry, WorkoutSession, WorkoutSet,
        )

        self.alice = User.objects.create_user("export-alice@example.com", "long-alice-password")
        self.bob = User.objects.create_user("export-bob@example.com", "long-bob-password")
        self.household = create_household(owner=self.alice, name="Export household")
        HouseholdMembership.objects.create(
            household=self.household,
            user=self.bob,
            role=HouseholdMembership.Role.MEMBER,
            status=HouseholdMembership.Status.ACTIVE,
        )
        alice_profile = PersonalProfile.objects.get(user=self.alice)
        alice_profile.share_weight_history = True
        alice_profile.save(update_fields=("share_weight_history", "updated_at"))

        WeightEntry.objects.create(owner=self.alice, household=self.household, weight_kg="90.00")
        self.bob_weight = WeightEntry.objects.create(owner=self.bob, weight_kg="75.00")
        FoodEntry.objects.create(owner=self.bob, food_name="Private breakfast", calories_kcal="350")
        grocery = GroceryList.objects.create(owner=self.bob, name="My private list")
        GroceryItem.objects.create(grocery_list=grocery, name="Apples", quantity="4")
        workout = WorkoutSession.objects.create(owner=self.bob, title="My workout")
        WorkoutSet.objects.create(
            session=workout,
            exercise_key="squat",
            exercise_name="Squat",
            set_number=1,
            reps=10,
            weight_kg="40.00",
        )

    def test_export_requires_authentication(self):
        response = self.client.get("/api/v1/export/")
        self.assertIn(response.status_code, (401, 403))

    def test_export_contains_only_current_accounts_owned_records_and_nested_data(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get("/api/v1/export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response.data["format"], "fitstart-v2-export")
        self.assertEqual(
            [row["id"] for row in response.data["records"]["weight_entries"]],
            [self.bob_weight.pk],
        )
        self.assertNotIn("90.00", str(response.data["records"]["weight_entries"]))
        self.assertEqual(
            response.data["records"]["food_entries"][0]["food_name"],
            "Private breakfast",
        )
        self.assertEqual(
            response.data["records"]["grocery_lists"][0]["items"][0]["name"],
            "Apples",
        )
        self.assertEqual(
            response.data["records"]["workout_sessions"][0]["sets"][0]["exercise_name"],
            "Squat",
        )
        serialized = str(response.data)
        self.assertNotIn("cloudConfig", serialized)
        self.assertNotIn("gist_token", serialized.lower())
        self.assertNotIn("password", serialized.lower())


class CatalogApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command("import_v1_catalog")

    def setUp(self):
        self.alice = User.objects.create_user("catalog-alice@example.com", "long-alice-password")
        self.bob = User.objects.create_user("catalog-bob@example.com", "long-bob-password")

    def test_recipe_catalog_can_be_filtered_by_diet_and_slot(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.get("/api/v1/recipes/?diet_style=vegetarian&slot=Breakfast")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 10)
        self.assertTrue(all(row["diet_style"] == "vegetarian" for row in response.data))
        self.assertTrue(all(row["slot"] == "Breakfast" for row in response.data))
        first = response.data[0]
        self.assertIn("portions", first)
        self.assertIn("base_macros", first)
        self.assertIn("steps", first)
        self.assertIn("tip", first)

    def test_recipe_favorites_are_private_to_each_user(self):
        self.client.force_authenticate(user=self.alice)
        recipe = self.client.get("/api/v1/recipes/?diet_style=balanced&slot=Breakfast").data[0]
        created = self.client.post(
            "/api/v1/recipes/favorites/",
            {"recipe_id": recipe["id"]},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertTrue(created.data["recipe"]["is_favorite"])
        listed = self.client.get("/api/v1/recipes/favorites/")
        self.assertEqual(len(listed.data), 1)

        self.client.force_authenticate(user=self.bob)
        self.assertEqual(self.client.get("/api/v1/recipes/favorites/").data, [])
        detail = self.client.get(f"/api/v1/recipes/{recipe['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.data["is_favorite"])

        self.client.force_authenticate(user=self.alice)
        deleted = self.client.delete(f"/api/v1/recipes/favorites/{recipe['id']}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get("/api/v1/recipes/favorites/").data, [])

    def test_exercise_catalog_and_nested_workout_routines_are_complete(self):
        self.client.force_authenticate(user=self.alice)
        exercises = self.client.get("/api/v1/exercises/")
        self.assertEqual(exercises.status_code, 200)
        self.assertEqual(len(exercises.data), 80)
        self.assertTrue(exercises.data[0]["steps"])

        routines = self.client.get("/api/v1/workout-routines/?mode=home&level=beginner")
        self.assertEqual(routines.status_code, 200)
        self.assertEqual(len(routines.data), 4)
        self.assertEqual(len(routines.data[0]["exercise_links"]), 5)
        first_exercise = routines.data[0]["exercise_links"][0]["exercise"]
        self.assertTrue(first_exercise["steps"])
        self.assertTrue(first_exercise["modification"])
        self.assertTrue(first_exercise["common_mistake"])
