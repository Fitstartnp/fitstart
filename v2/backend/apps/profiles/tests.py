from django.test import TestCase

from apps.accounts.models import User
from .models import PersonalProfile


class PersonalProfileTests(TestCase):
    def test_new_account_gets_private_default_profile(self):
        user = User.objects.create_user("profile@example.com", "long-profile-password")
        profile = PersonalProfile.objects.get(user=user)
        self.assertFalse(profile.share_weight_history)
        self.assertFalse(profile.share_body_measurements)
        self.assertFalse(profile.share_food_diary)
        self.assertFalse(profile.share_workout_plans)
        self.assertFalse(profile.share_meal_plans)
        self.assertFalse(profile.share_grocery_lists)
