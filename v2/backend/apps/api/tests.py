from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.households.services import create_household


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
