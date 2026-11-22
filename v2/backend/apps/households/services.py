from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .models import Household, HouseholdInvitation, HouseholdMembership


def create_household(*, owner, name: str) -> Household:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("A household name is required.")
    household = Household.objects.create(name=clean_name[:100], created_by=owner)
    HouseholdMembership.objects.create(
        household=household,
        user=owner,
        role=HouseholdMembership.Role.OWNER,
        status=HouseholdMembership.Status.ACTIVE,
    )
    return household


def create_invitation(*, actor, household, email: str, role: str = HouseholdInvitation.Role.MEMBER):
    membership = HouseholdMembership.objects.filter(
        household=household,
        user=actor,
        status=HouseholdMembership.Status.ACTIVE,
        role__in=(HouseholdMembership.Role.OWNER, HouseholdMembership.Role.ADMIN),
    ).first()
    if membership is None:
        raise PermissionDenied("Only household owners or administrators can invite members.")
    if role not in (HouseholdInvitation.Role.ADMIN, HouseholdInvitation.Role.MEMBER):
        raise ValueError("Invitations cannot grant household owner permissions.")
    if HouseholdMembership.objects.filter(
        household=household,
        user__email__iexact=email.strip(),
        status=HouseholdMembership.Status.ACTIVE,
    ).exists():
        raise ValueError("This email already belongs to the household.")
    return HouseholdInvitation.issue(
        household=household,
        invited_email=email,
        role=role,
        created_by=actor,
        expires_at=timezone.now() + timedelta(days=7),
    )
