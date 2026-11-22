from django.contrib import admin

from .models import PersonalProfile


@admin.register(PersonalProfile)
class PersonalProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "unit_system", "created_at")
    search_fields = ("user__email", "display_name")
    readonly_fields = ("created_at", "updated_at")
