from django import forms
from django.contrib import admin

from ..models import (
    Country,
    Institution,
    InstitutionBranch,
    Party,
    PartyPosition,
    PartyPositionTimeFrame,
)
from ._timeframe import (
    CurrentSettingsInlineMixin,
    TimeFrameInlineAdminMixin,
    TimeFrameInlineFormSet,
    TimelineSelectionFormMixin,
)


FRAME_FIELDS = ("valid_from", "valid_to", "timeline_selection")


class PartyPositionInlineForm(TimelineSelectionFormMixin, forms.ModelForm):
    timeline_selection = TimelineSelectionFormMixin.timeline_selection_field()
    valid_from = forms.DateTimeField(
        required=False,
        label="Valid from",
        help_text="Leave both bounds empty for an open-ended time frame.",
    )
    valid_to = forms.DateTimeField(required=False, label="Valid to")

    class Meta:
        model = PartyPosition
        fields = ("position", "chamber", "valid_from", "valid_to")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_new = self.instance.pk is None
        frame = self.frame_to_edit()
        if frame is not None and frame.pk is not None:
            self.initial.setdefault("valid_from", frame.valid_from)
            self.initial.setdefault("valid_to", frame.valid_to)

    def frame_to_edit(self):
        if self.instance.pk is None:
            return None
        return self.instance.time_frames.order_by("id").first()

    def frame_changed(self) -> bool:
        return self.is_new or any(name in self.changed_data for name in FRAME_FIELDS)

    def time_frame(self) -> PartyPositionTimeFrame:
        frame = PartyPositionTimeFrame(
            subject=PartyPosition(
                pk=self.instance.pk,
                party_id=self.instance.party_id,
                chamber=self.cleaned_data.get("chamber"),
                position=self.cleaned_data.get("position"),
            ),
            valid_from=self.cleaned_data.get("valid_from"),
            valid_to=self.cleaned_data.get("valid_to"),
        )
        frame.pending_timeline_ids = self.selected_timeline_ids()
        return frame

    def save_time_frame(self):
        if self.cleaned_data.get("DELETE") or not self.instance.pk:
            return
        if not self.frame_changed():
            return
        self.instance.time_frames.all().delete()
        frame = PartyPositionTimeFrame.objects.create_for(
            self.instance,
            valid_from=self.cleaned_data.get("valid_from"),
            valid_to=self.cleaned_data.get("valid_to"),
        )
        frame.timelines.set(self.selected_timelines())


class PartyPositionInline(CurrentSettingsInlineMixin, admin.TabularInline):
    model = PartyPosition
    form = PartyPositionInlineForm
    formset = TimeFrameInlineFormSet
    extra = 0
    fields = ("position", "chamber", "valid_from", "valid_to", "timeline_selection")

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
class PartyAdmin(TimeFrameInlineAdminMixin, admin.ModelAdmin):
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
