from datetime import datetime
from typing import Iterable

from django.db import models, transaction
from django.db.models import Q

from ._timeline import VirtualTimeline
from ._subject import TimeFrameSubject


class TimeFrameQuerySet(models.QuerySet):
    def of(self, subject: TimeFrameSubject) -> "TimeFrameQuerySet":
        if not isinstance(subject, TimeFrameSubject):
            raise TypeError(f"{type(subject).__name__} cannot occupy a time frame")
        if subject.pk is None:
            return self.none()
        return self.filter(subject=subject)

    def create_for(self, subject: TimeFrameSubject, **kwargs) -> models.Model:
        """Create a time frame for the subject, without validation."""
        if not isinstance(subject, TimeFrameSubject):
            raise TypeError(f"{type(subject).__name__} cannot occupy a time frame")
        return self.create(subject=subject, **kwargs)

    def covering(self, at: datetime) -> "TimeFrameQuerySet":
        """The frames whose interval contains ``at``."""
        return self.filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=at),
            Q(valid_to__isnull=True) | Q(valid_to__gt=at),
        )

    def on_timeline(self, timeline: VirtualTimeline) -> "TimeFrameQuerySet":
        """The frames that apply to the timeline (linked or unrestricted)."""
        return self.filter(Q(timelines=timeline) | Q(timelines__isnull=True)).distinct()

    def active_on(self, timeline: VirtualTimeline, at: datetime) -> "TimeFrameQuerySet":
        """The frames that apply to the timeline and contain ``at``."""
        return self.on_timeline(timeline).covering(at)

    def occupy(
        self,
        subject: TimeFrameSubject,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        timelines: Iterable[VirtualTimeline] = (),
    ) -> models.Model:
        """
        Validate and create a time frame for the subject, restricted to the given
        timelines (no timelines: all timelines).
        """
        if not isinstance(subject, TimeFrameSubject):
            raise TypeError(f"{type(subject).__name__} cannot occupy a time frame")
        timelines = list(timelines)
        frame = self.model(
            subject=subject,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        frame.pending_timelines = timelines or None
        with transaction.atomic():
            frame.full_clean()
            frame.save()
            frame.timelines.set(timelines)
        return frame
