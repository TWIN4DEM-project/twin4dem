from django.contrib import admin
from ..models._settings import UserSettings, PartySettings


from django.core.exceptions import ValidationError
from django.db import transaction


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

    def save_related(self, request, form, formsets, change):
        with transaction.atomic():
            # Save parent object
            self.save_form(request, form, change)

            # Save all inline formsets
            for formset in formsets:
                self.save_formset(request, form, formset, change)

            # Now verify the constraint
            parliament = form.instance
            total_members = sum(p.member_count for p in parliament.parties.all())
            if total_members != parliament.parliament_size:
                raise ValidationError(
                    f"Sum of party member_count ({total_members}) must equal parliament_size ({parliament.parliament_size})."
                )
