from django.contrib import admin

from ._country import CountryInline
from ..models import (
    UserSettings,
    VirtualTimeline,
)


class VirtualTimelineInline(admin.TabularInline):
    model = VirtualTimeline
    extra = 0


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "user", "data_update_frequency")
    search_fields = ("label", "user__username")
    inlines = [VirtualTimelineInline, CountryInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)
