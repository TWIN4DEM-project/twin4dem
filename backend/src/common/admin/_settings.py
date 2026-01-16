from django import forms
from django.contrib import admin
from ..models._settings import UserSettings, PartySettings


from django.core.exceptions import ValidationError


class UserSettingsAdminForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        # fields = '__all__'
        exclude = ["parties"]


class PartySettingsInlineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        """Validate that sum of member_count equals parliament_size."""
        super().clean()

        total_members = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                total_members += form.cleaned_data.get("member_count", 0)

        parliament_size = self.instance.parliament_size

        # Validate the constraint
        if total_members != parliament_size:
            raise ValidationError(
                f"Sum of party member_count ({total_members}) must equal "
                f"parliament_size ({parliament_size})."
            )


class PartySettingsInline(admin.TabularInline):
    model = PartySettings
    formset = PartySettingsInlineFormSet
    extra = 0


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    form = UserSettingsAdminForm
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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is not None:
            obj._skip_parliament_validation = True
        return form
