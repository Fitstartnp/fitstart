from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from .models import HouseholdInvitation, HouseholdMembership
from .services import accept_invitation, create_household, create_invitation


class HouseholdServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@example.com", "long-owner-password")
        self.member = User.objects.create_user("member@example.com", "long-member-password")
        self.household = create_household(owner=self.owner, name="Our household")

    def test_creator_is_owner(self):
        membership = HouseholdMembership.objects.get(household=self.household, user=self.owner)
        self.assertEqual(membership.role, HouseholdMembership.Role.OWNER)

    def test_invitation_stores_only_digest_and_returns_raw_token_once(self):
        invitation, raw_token = create_invitation(
            actor=self.owner,
            household=self.household,
            email="member@example.com",
        )
        invitation.refresh_from_db()
        self.assertNotEqual(invitation.token_digest, raw_token)
        self.assertTrue(invitation.matches_token(raw_token))
        self.assertTrue(invitation.is_usable)

    def test_verified_invited_user_can_accept_once(self):
        invitation, raw_token = create_invitation(
            actor=self.owner,
            household=self.household,
            email=self.member.email,
        )
        self.member.email_verified_at = timezone.now()
        self.member.save(update_fields=("email_verified_at",))
        membership = accept_invitation(user=self.member, raw_token=raw_token)
        self.assertEqual(membership.household_id, self.household.id)
        self.assertEqual(membership.role, HouseholdMembership.Role.MEMBER)
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)
        with self.assertRaises(PermissionDenied):
            accept_invitation(user=self.member, raw_token=raw_token)

    def test_invitation_cannot_be_accepted_by_another_email(self):
        invitation, raw_token = create_invitation(
            actor=self.owner,
            household=self.household,
            email="other@example.com",
        )
        self.member.email_verified_at = timezone.now()
        self.member.save(update_fields=("email_verified_at",))
        with self.assertRaises(PermissionDenied):
            accept_invitation(user=self.member, raw_token=raw_token)
        self.assertFalse(
            HouseholdMembership.objects.filter(household=self.household, user=self.member).exists()
        )

    def test_member_cannot_invite(self):
        HouseholdMembership.objects.create(
            household=self.household,
            user=self.member,
            role=HouseholdMembership.Role.MEMBER,
        )
        with self.assertRaises(PermissionDenied):
            create_invitation(
                actor=self.member,
                household=self.household,
                email="third@example.com",
            )

    def test_expired_invitation_is_not_usable(self):
        invitation = HouseholdInvitation.objects.create(
            household=self.household,
            invited_email="expired@example.com",
            role=HouseholdInvitation.Role.MEMBER,
            token_digest=HouseholdInvitation.digest_token("one-time-token"),
            created_by=self.owner,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertFalse(invitation.is_usable)
