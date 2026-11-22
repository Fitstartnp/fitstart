from django.contrib import admin

from .models import Household, HouseholdInvitation, HouseholdMembership


class HouseholdMembershipInline(admin.TabularInline):
    model = HouseholdMembership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at", "archived_at")
    search_fields = ("name", "created_by__email")
    inlines = (HouseholdMembershipInline,)


@admin.register(HouseholdInvitation)
class HouseholdInvitationAdmin(admin.ModelAdmin):
    list_display = ("invited_email", "household", "role", "created_by", "created_at", "expires_at", "accepted_at")
    search_fields = ("invited_email", "household__name")
    readonly_fields = ("token_digest", "created_at", "accepted_at")
