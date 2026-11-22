from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.households.models import HouseholdMembership
from apps.households.services import create_household
from apps.profiles.models import PersonalProfile
from .models import FoodEntry, WeightEntry


class PersonalRecordSharingTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice@example.com", "long-alice-password")
        self.bob = User.objects.create_user("bob@example.com", "long-bob-password")
        self.charlie = User.objects.create_user("charlie@example.com", "long-charlie-password")
        self.home = create_household(owner=self.alice, name="Alice and Bob")
        HouseholdMembership.objects.create(
            household=self.home,
            user=self.bob,
            role=HouseholdMembership.Role.MEMBER,
            status=HouseholdMembership.Status.ACTIVE,
        )
        self.other_home = create_household(owner=self.charlie, name="Charlie's home")

    def test_weight_entry_is_private_by_default(self):
        entry = WeightEntry.objects.create(owner=self.alice, weight_kg="82.40")
        self.assertEqual(list(WeightEntry.visible_to(self.alice)), [entry])
        self.assertFalse(WeightEntry.visible_to(self.bob).exists())
        self.assertFalse(WeightEntry.visible_to(self.charlie).exists())

    def test_weight_cannot_be_shared_until_owner_enables_category(self):
        entry = WeightEntry(owner=self.alice, household=self.home, weight_kg="82.40")
        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_household_member_can_see_only_explicitly_shared_weight_entries(self):
        profile = PersonalProfile.objects.get(user=self.alice)
        profile.share_weight_history = True
        profile.save(update_fields=("share_weight_history", "updated_at"))
        entry = WeightEntry(owner=self.alice, household=self.home, weight_kg="82.40")
        entry.full_clean()
        entry.save()
        self.assertTrue(WeightEntry.visible_to(self.alice).filter(pk=entry.pk).exists())
        self.assertTrue(WeightEntry.visible_to(self.bob).filter(pk=entry.pk).exists())
        self.assertFalse(WeightEntry.visible_to(self.charlie).filter(pk=entry.pk).exists())

    def test_food_diary_remains_private_when_weight_history_is_shared(self):
        profile = PersonalProfile.objects.get(user=self.alice)
        profile.share_weight_history = True
        profile.save(update_fields=("share_weight_history", "updated_at"))
        entry = FoodEntry.objects.create(owner=self.alice, food_name="Example meal")
        self.assertFalse(FoodEntry.visible_to(self.bob).filter(pk=entry.pk).exists())
        self.assertTrue(FoodEntry.visible_to(self.alice).filter(pk=entry.pk).exists())

    def test_owner_must_be_member_of_household_to_share_record(self):
        profile = PersonalProfile.objects.get(user=self.charlie)
        profile.share_weight_history = True
        profile.save(update_fields=("share_weight_history", "updated_at"))
        entry = WeightEntry(owner=self.charlie, household=self.home, weight_kg="74.00")
        with self.assertRaises(ValidationError):
            entry.full_clean()
