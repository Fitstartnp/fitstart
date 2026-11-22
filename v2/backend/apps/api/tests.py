from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import User
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
