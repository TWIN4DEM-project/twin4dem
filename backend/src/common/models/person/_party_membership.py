from django.db import models
from django.db.models import F, Q

from common.models import Party, PartyPosition, PartyPositionType
from common.models.timeline import (
    TimeFrameSubject,
    TimeFrameSubjectQuerySet,
    TimeFrameModel,
    TimelineMap,
    VirtualTimeline,
)


class PartyMembershipQuerySet(TimeFrameSubjectQuerySet):
    def related_positions(
        self,
        parties: models.QuerySet[Party] | None = None,
        timeline: VirtualTimeline | int | None = None,
    ) -> models.QuerySet[PartyPosition]:
        """The positions of the memberships' parties that apply to ``timeline``.

        A position is included when a membership period and the position's
        frames share a timeline. Frames without timeline links apply to all
        timelines. Without a timeline, every shared timeline is considered.
        """
        membership_on_all_timelines = Q(party__party_members__timelines__isnull=True)
        position_on_all_timelines = Q(time_frames__timelines__isnull=True)
        if timeline is None:
            all_matching_member_pos_timelines = Q(
                time_frames__timelines=F("party__party_members__timelines")
            )
            applies = (
                membership_on_all_timelines
                | position_on_all_timelines
                | all_matching_member_pos_timelines
            )
        else:
            member_pos_matching_timelines = Q(party__party_members__timelines=timeline)
            pos_matches_input_timeline = Q(time_frames__timelines=timeline)
            applies = (member_pos_matching_timelines | membership_on_all_timelines) & (
                pos_matches_input_timeline | position_on_all_timelines
            )
        scope = Q(party__party_members__subject__in=self)
        if parties is not None:
            scope &= Q(party__in=parties)
        return PartyPosition.objects.filter(scope & applies).distinct()


class PartyMembership(TimeFrameSubject):
    sibling_fields = ("person",)

    person = models.ForeignKey(
        "Person", on_delete=models.CASCADE, related_name="party_membership"
    )

    objects = PartyMembershipQuerySet.as_manager()

    @property
    def time_frames(self) -> models.Manager:
        return self.periods

    def most_recent_positions(
        self, timeline: VirtualTimeline | int | None = None
    ) -> TimelineMap[PartyPositionType]:
        """Fetch the most recent positions of the current party member.

        If a timeline is passed then the results are restricted to that timeline.
        If there are no positions, an empty dict is returned.
        """
        memberships = type(self).objects.filter(pk=self.pk)
        positions = memberships.related_positions(timeline=timeline)
        qs = positions.most_recent(timeline, per=(), per_timeline=True)
        return TimelineMap(
            (timeline_id, PartyPositionType(position))
            for timeline_id, position in qs.values_list(
                "time_frames__timelines", "position"
            )
        )


class PartyMembershipPeriod(TimeFrameModel):
    subject = models.ForeignKey(
        PartyMembership, on_delete=models.CASCADE, related_name="periods"
    )
    party = models.ForeignKey(
        "Party", on_delete=models.CASCADE, related_name="party_members"
    )
