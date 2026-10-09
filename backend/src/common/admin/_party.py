from django.contrib import admin
from ..models import PartyPosition
from ..models._institution import Institution
from ..models._party import Party
from ..models._settings import Country, InstitutionBranch


class PartyPositionInline(admin.TabularInline):
    model = PartyPosition
    extra = 0

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "chamber":
            chambers = Institution.objects.filter(
                kind__branch=InstitutionBranch.LEGISLATIVE
            )
            if not request.user.is_superuser:
                chambers = chambers.filter(
                    kind__country__user_settings__user=request.user
                )
            kwargs["queryset"] = chambers
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "country")
    search_fields = ("label", "country__name")
    inlines = [PartyPositionInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(country__user_settings__user=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "country" and not request.user.is_superuser:
            kwargs["queryset"] = Country.objects.filter(
                user_settings__user=request.user
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
