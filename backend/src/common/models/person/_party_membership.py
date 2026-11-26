from django.db import models

from common.models import PartyPosition, PartyPositionType
from common.models.timeline import (
    TimeFrameSubject,
    TimeFrameModel,
    TimelineMap,
    VirtualTimeline,
)


class PartyMembership(TimeFrameSubject):
    sibling_fields = ("person",)

    person = models.ForeignKey(
        "Person", on_delete=models.CASCADE, related_name="party_membership"
    )

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
        qs = PartyPosition.objects.filter(party__in=self.periods.values("party"))
        timelines = set(
            v
            for d in self.periods.values("timelines")
            for v in d.values()
            if v is not None
        )
        if len(timelines) > 0:
            qs = qs.filter(time_frames__timelines__in=timelines)
        qs = qs.most_recent(timeline, per=(), per_timeline=True)
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
