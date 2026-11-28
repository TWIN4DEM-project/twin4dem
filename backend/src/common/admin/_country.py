from functools import partialmethod

from django import forms
from django.contrib import admin

from common.models import Country, InstitutionKind, Party, UserSettings


class CountryInline(admin.TabularInline):
    model = Country
    extra = 0
    show_change_link = True


class InstitutionTaxonomyInline(admin.TabularInline):
    model = InstitutionKind
    extra = 0


class PartyInline(admin.TabularInline):
    model = Party
    extra = 0
    show_change_link = True


class CountryAdminForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ("name",)

    def __init__(self, *args, user_settings_id: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            self.instance.user_settings_id = user_settings_id


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    form = CountryAdminForm
    list_display = ("id", "name")
    search_fields = ("name",)
    readonly_fields = ("user_settings",)
    inlines = [InstitutionTaxonomyInline, PartyInline]

    def get_form(self, request, obj=None, change=False, **kwargs):
        form_cls = super().get_form(request, obj, change, **kwargs)
        user_settings_id = getattr(request.current_settings, "pk", None)
        return type(
            form_cls.__name__,
            (form_cls,),
            {
                "__init__": partialmethod(
                    form_cls.__init__, user_settings_id=user_settings_id
                )
            },
        )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        settings = getattr(request, "current_settings", None)
        if settings is None:
            return qs.none()
        return qs.filter(user_settings=settings)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user_settings" and not request.user.is_superuser:
            kwargs["queryset"] = UserSettings.objects.filter(user=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
