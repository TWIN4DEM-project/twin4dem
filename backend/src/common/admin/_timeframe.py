from django.contrib import admin
from django.db.models import Q

from ..models._institution import Institution
from ..models._party import PartyPosition
from ..models._settings import VirtualTimeline
from ..models._timeframe import TimeFrame, TimeFrameSubjectType, TimelineTimeFrame


class TimelineTimeFrameInline(admin.TabularInline):
    model = TimelineTimeFrame
    extra = 0

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "virtual_timeline" and not request.user.is_superuser:
            kwargs["queryset"] = VirtualTimeline.objects.filter(
                user_settings__user=request.user
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(TimeFrame)
class TimeFrameAdmin(admin.ModelAdmin):
    list_display = ("id", "subject_type", "subject_id", "valid_from", "valid_to")
    list_filter = ("subject_type",)
    inlines = [TimelineTimeFrameInline]

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
