from django import forms
from django.contrib import admin
from django.db.models import Q

from ..models._institution import Institution
from ..models import PartyPosition
from ..models._settings import VirtualTimeline
from ..models._timeframe import TimeFrame, TimeFrameSubjectType


class TimeFrameAdminForm(forms.ModelForm):
    # not the `timelines` model field: the frame must be validated together with
    # its timelines, before anything is saved
    timeline_selection = forms.ModelMultipleChoiceField(
        queryset=VirtualTimeline.objects.select_related("user_settings"),
        required=False,
        label="Timelines",
        help_text="Leave empty to apply the time frame to all timelines.",
    )

    # restricts the selectable timelines; set per request by TimeFrameAdmin
    timeline_queryset = None

    class Meta:
        model = TimeFrame
        fields = ("subject_type", "subject_id", "valid_from", "valid_to")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.timeline_queryset is not None:
            self.fields["timeline_selection"].queryset = self.timeline_queryset
        if self.instance.pk is not None:
            self.initial["timeline_selection"] = self.instance.timelines.all()

    def clean(self):
        cleaned_data = super().clean()
        self.instance.pending_timeline_ids = [
            timeline.pk for timeline in cleaned_data.get("timeline_selection", [])
        ]
        return cleaned_data


@admin.register(TimeFrame)
class TimeFrameAdmin(admin.ModelAdmin):
    form = TimeFrameAdminForm
    list_display = ("id", "subject_type", "subject_id", "valid_from", "valid_to")
    list_filter = ("subject_type",)

    def get_form(self, request, obj=None, **kwargs):
        # get_form() builds a new form class per request, so this is not shared
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            form.timeline_queryset = VirtualTimeline.objects.filter(
                user_settings__user=request.user
            )
        return form

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.timelines.set(form.cleaned_data["timeline_selection"])

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        institution_ids = Institution.objects.filter(
            institution_taxonomy__country__user_settings__user=request.user
        ).values("id")
        party_position_ids = PartyPosition.objects.filter(
            party__country__user_settings__user=request.user
        ).values("id")
        return qs.filter(
            Q(
                subject_type=TimeFrameSubjectType.INSTITUTION,
                subject_id__in=institution_ids,
            )
            | Q(
                subject_type=TimeFrameSubjectType.PARTY_POSITION,
                subject_id__in=party_position_ids,
            )
        )
