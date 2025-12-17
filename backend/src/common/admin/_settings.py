from django.contrib import admin
from ..models._settings import UserSettings, PartySettings


class PartySettingsInline(admin.TabularInline):
    model = PartySettings
    extra = 0


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "label",
        "user",
        "government_size",
        "parliament_size",
        "court_size",
        "abstention_threshold",
    )
    search_fields = ("label", "user__username")
    inlines = [PartySettingsInline]
