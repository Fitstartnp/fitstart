from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase


class DashboardRenderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "dashboard@example.com",
            "long-dashboard-password",
        )

    def test_dashboard_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_authenticated_user_can_render_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard.html")
        self.assertContains(response, "Your FitStart space")
        self.assertContains(response, "weightForm")
        self.assertContains(response, "profileForm")
        self.assertContains(response, "householdForm")
        self.assertContains(response, "measureForm")
        self.assertContains(response, "waterForm")
        self.assertContains(response, "mealForm")
        self.assertContains(response, "groceryItemForm")
        self.assertContains(response, "workoutSetForm")
        self.assertContains(response, "fastingForm")
        self.assertContains(response, "v1ImportForm")
        self.assertContains(response, "confirmV1ImportButton")
        self.assertContains(response, "exportDataButton")
        self.assertContains(response, "profileAge")
        self.assertContains(response, "fitstart/app.js")
        self.assertContains(response, "fitstart/app.css")

    def test_frontend_assets_exist_in_staticfiles_finder(self):
        self.assertIsNotNone(finders.find("fitstart/app.js"))
        self.assertIsNotNone(finders.find("fitstart/app.css"))
