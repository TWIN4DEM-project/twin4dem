from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import F, Q

from ._spec import ALWAYS, FrameSpec, _format_interval, _format_timelines
from ._subject import TimeFrameSubject
from ._timeframe_qs import TimeFrameQuerySet
from ._timeline import VirtualTimeline


class TimeFrameModel(models.Model):
    """An interval ``[valid_from, valid_to)`` defined on one or more timelines.

    A missing bound means the interval is open-ended. Concrete subclasses
    point to their subject through a real foreign key named ``subject`` with
    ``related_name="time_frames"``. A time frame without timeline links applies
    to all timelines of the subject's global context, including timelines added
    later.
    """

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_valid_from_before_valid_to",
                condition=Q(valid_from__isnull=True)
                | Q(valid_to__isnull=True)
                | Q(valid_from__lt=F("valid_to")),
            ),
        ]

    if TYPE_CHECKING:
        subject_id: int
        subject: TimeFrameSubject

    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    timelines = models.ManyToManyField(
        to=VirtualTimeline,
        related_name="%(class)s_time_frames",
        blank=True,
    )

    objects = TimeFrameQuerySet.as_manager()

    # timelines to validate against instead of the stored links (empty: all
    # timelines); set before full_clean() when links are saved together with
    # the frame
    pending_timeline_ids: list[int] | None = None

    def __str__(self):
        return (
            f"{self._meta.model_name}={self.subject_id} {_format_interval(self.spec)}"
        )

    @property
    def spec(self) -> FrameSpec:
        timeline_ids = None
        if self.pk is not None:
            timeline_ids = frozenset(timeline.pk for timeline in self.timelines.all())
        return FrameSpec(self.valid_from, self.valid_to, timeline_ids or None)

    @property
    def is_on_all_timelines(self) -> bool:
        if self.pk is None:
            return True
        if not self.timelines.exists():
            return True
        return False

    def get_timelines(self) -> models.QuerySet[VirtualTimeline]:
        """The timelines this time frame is active on."""
        if self.is_on_all_timelines:
            return VirtualTimeline.objects.filter(
                user_settings_id=self.subject.time_frame_user_settings_id()
            )
        return self.timelines.all()

    def validate_time_frame(self, *, ignore_frame_ids: Iterable[int] = ()) -> None:
        """Validate this frame of its subject on its timelines.

        A subject occupies at most one time frame per timeline. Its siblings
        may not be active at the same time on the same timeline. A sibling
        without time frames is active at all times on all timelines.
        """
        if self.pending_timeline_ids is not None:
            timeline_ids = self.pending_timeline_ids or None
        else:
            timeline_ids = self.spec.timeline_ids
        candidate = FrameSpec(
            self.valid_from,
            self.valid_to,
            None if timeline_ids is None else frozenset(timeline_ids),
        )
        user_timeline_labels = dict(
            VirtualTimeline.objects.filter(
                user_settings_id=self.subject.time_frame_user_settings_id()
            ).values_list("id", "label")
        )

        if candidate.timeline_ids is not None and not candidate.timeline_ids.issubset(
            user_timeline_labels.keys()
        ):
            raise ValidationError(
                "The timelines must belong to the same global context as the "
                "time frame's subject."
            )

        errors = []
        own_frames = type(self).objects.of(self.subject).prefetch_related("timelines")
        if self.pk is not None:
            own_frames = own_frames.exclude(pk=self.pk)
        if ignore_frame_ids:
            own_frames = own_frames.exclude(pk__in=ignore_frame_ids)
        for other in own_frames:
            if candidate.shares_timeline_with(other.spec):
                errors.append(
                    f"{self.subject.time_frame_label()} already occupies the time "
                    f"frame {_format_interval(other.spec)} on "
                    f"{_format_timelines(candidate.shared_timelines(other.spec), user_timeline_labels)}."
                )

        siblings = list(self.subject.time_frame_siblings())
        sibling_frames = defaultdict(list)
        for sibling_frame in (
            type(self)
            .objects.filter(subject__in=siblings)
            .prefetch_related("timelines")
        ):
            sibling_frames[sibling_frame.subject_id].append(sibling_frame.spec)

        for sibling in siblings:
            for spec in sibling_frames.get(sibling.pk) or [ALWAYS]:
                if not (
                    candidate.shares_timeline_with(spec)
                    and candidate.overlaps_in_time(spec)
                ):
                    continue
                if spec is ALWAYS:
                    errors.append(
                        f"{sibling.time_frame_label()} has no time frame, so it is "
                        f"active at all times on all timelines."
                    )
                else:
                    errors.append(
                        f"Overlaps with {sibling.time_frame_label()} "
                        f"{_format_interval(spec)} on "
                        f"{_format_timelines(candidate.shared_timelines(spec), user_timeline_labels)}."
                    )

        if errors:
            raise ValidationError(errors)

    def clean(self):
        super().clean()
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_from >= self.valid_to
        ):
            raise ValidationError(
                {"valid_to": "The time frame must end after it starts."}
            )
        if self.subject_id is None:
            return
        try:
            self.subject
        except ObjectDoesNotExist:
            return

        self.validate_time_frame()
