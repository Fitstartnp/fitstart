from django.test import TestCase

from .models import User


class UserManagerTests(TestCase):
    def test_email_is_normalized_and_username_is_not_required(self):
        user = User.objects.create_user("FitStart@Example.com", "a-long-test-password")
        self.assertEqual(user.email, "FitStart@example.com")
        self.assertTrue(user.check_password("a-long-test-password"))
        self.assertFalse(hasattr(user, "username"))

    def test_passwordless_user_has_unusable_password(self):
        user = User.objects.create_user("no-password@example.com")
        self.assertFalse(user.has_usable_password())
