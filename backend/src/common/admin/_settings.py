from django.contrib import admin
from ..models._party import Party
from ..models._settings import (
    UserSettings,
    VirtualTimeline,
    Country,
    InstitutionKind,
)


class VirtualTimelineInline(admin.TabularInline):
    model = VirtualTimeline
    extra = 0


class CountryInline(admin.TabularInline):
    model = Country
    extra = 0
    show_change_link = True


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


class InstitutionTaxonomyInline(admin.TabularInline):
    model = InstitutionKind
    extra = 0


class PartyInline(admin.TabularInline):
    model = Party
    extra = 0
    show_change_link = True


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "user_settings")
    search_fields = ("name",)
    inlines = [InstitutionTaxonomyInline, PartyInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user_settings__user=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user_settings" and not request.user.is_superuser:
            kwargs["queryset"] = UserSettings.objects.filter(user=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
