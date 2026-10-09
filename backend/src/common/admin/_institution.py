from django.contrib import admin
from ..models._institution import Institution
from ..models._settings import InstitutionKind


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "kind", "size")
    list_filter = ("kind__branch",)
    search_fields = ("label", "kind__institution_name")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(kind__country__user_settings__user=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "kind" and not request.user.is_superuser:
            kwargs["queryset"] = InstitutionKind.objects.filter(
                country__user_settings__user=request.user
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
