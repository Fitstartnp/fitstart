from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db import transaction

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



@transaction.atomic
def accept_invitation(*, user, raw_token: str):
    """Accept a single-use invitation only for the verified invited email."""
    digest = HouseholdInvitation.digest_token(raw_token)
    try:
        invitation = HouseholdInvitation.objects.select_for_update().get(token_digest=digest)
    except HouseholdInvitation.DoesNotExist as exc:
        raise PermissionDenied("This invitation is invalid or has expired.") from exc

    if not invitation.is_usable or not invitation.matches_token(raw_token):
        raise PermissionDenied("This invitation is invalid or has expired.")
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Sign in with the invited account before accepting.")
    if not user.email_verified_at:
        raise PermissionDenied("Verify your email address before accepting this invitation.")
    if user.email.strip().lower() != invitation.invited_email.strip().lower():
        raise PermissionDenied("This invitation was issued to a different email address.")

    membership, _ = HouseholdMembership.objects.update_or_create(
        household=invitation.household,
        user=user,
        defaults={
            "role": invitation.role,
            "status": HouseholdMembership.Status.ACTIVE,
        },
    )
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=("accepted_at",))
    return membership
