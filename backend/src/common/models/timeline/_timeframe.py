from collections import defaultdict
from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import F, Q

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
        return f"{self._meta.model_name}={self.subject_id} {self.format_interval()}"

    def format_interval(self) -> str:
        return f"[{self.valid_from or '-inf'}, {self.valid_to or '+inf'})"

    @property
    def timeline_ids(self) -> frozenset[int] | None:
        """The timelines the frame is restricted to; None means all timelines.

        Reads ``pending_timeline_ids`` when set, i.e. before the links are
        saved.
        """
        if self.pending_timeline_ids is not None:
            return frozenset(self.pending_timeline_ids) or None
        if self.pk is None:
            return None
        return frozenset(timeline.pk for timeline in self.timelines.all()) or None

    @property
    def is_on_all_timelines(self) -> bool:
        if (
            self.pending_timeline_ids is not None
            and len(self.pending_timeline_ids) == 0
        ):
            return True
        if self.pk is None:
            return True
        if self.timeline_ids is None:
            return True
        return False

    def overlaps(self, other: "TimeFrameModel") -> bool:
        """Whether the two frames' intervals intersect (the ends are excluded)."""
        if not self.shares_timeline_with(other):
            return False
        self_start_before_other_end = (
            self.valid_from is None
            or other.valid_to is None
            or self.valid_from < other.valid_to
        )
        other_start_before_self_end = (
            other.valid_from is None
            or self.valid_to is None
            or other.valid_from < self.valid_to
        )
        return self_start_before_other_end and other_start_before_self_end

    def _shared_timeline_ids(self, other: "TimeFrameModel") -> frozenset[int] | None:
        """The timelines both frames are on (None: all timelines)."""
        mine, others = self.timeline_ids, other.timeline_ids
        if mine is None:
            return others
        if others is None:
            return mine
        return mine & others

    def shares_timeline_with(self, other: "TimeFrameModel") -> bool:
        shared_ids = self._shared_timeline_ids(other)
        return shared_ids is None or len(shared_ids) > 0

    def format_timelines(self, other: "TimeFrameModel", labels: dict[int, str]) -> str:
        """The timelines two frames share, in error messages."""
        shared_ids = self._shared_timeline_ids(other)
        if shared_ids is None:
            return "all timelines"
        names = sorted(f"'{labels.get(i, i)}'" for i in shared_ids)
        return ("timeline " if len(names) == 1 else "timelines ") + ", ".join(names)

    def get_timelines(self) -> models.QuerySet[VirtualTimeline]:
        """The timelines this time frame is active on."""
        if self.is_on_all_timelines:
            return VirtualTimeline.objects.filter(
                user_settings_id=self.subject.time_frame_user_settings_id()
            )
        return self.timelines.all()

    def validate_time_frame(self) -> None:
        """Validate this frame of its subject on its timelines.

        A subject occupies at most one time frame per timeline. Its siblings
        may not be active at the same time on the same timeline. A sibling
        without time frames is active at all times on all timelines.
        """
        user_timeline_labels = dict(
            VirtualTimeline.objects.filter(
                user_settings_id=self.subject.time_frame_user_settings_id()
            ).values_list("id", "label")
        )

        timeline_ids = self.timeline_ids
        if timeline_ids is not None and not timeline_ids.issubset(
            user_timeline_labels.keys()
        ):
            raise ValidationError(
                "The timelines must belong to the same global context as the "
                "time frame's subject."
            )

        errors = []
        same_subject_timeframes = (
            type(self).objects.of(self.subject).prefetch_related("timelines")
        )
        if self.pk is not None:
            same_subject_timeframes = same_subject_timeframes.exclude(pk=self.pk)
        err_template = "{} already occupies the time frame {} on {}."
        for other in same_subject_timeframes:
            if not self.shares_timeline_with(other):
                continue
            errors.append(
                err_template.format(
                    self.subject.time_frame_label(),
                    other.format_interval(),
                    self.format_timelines(other, user_timeline_labels),
                )
            )

        siblings = list(self.subject.siblings())
        sibling_frames = defaultdict(list)
        for sibling_frame in self.subject.sibling_time_frames().prefetch_related(
            "timelines"
        ):
            sibling_frames[sibling_frame.subject_id].append(sibling_frame)

        for sibling in siblings:
            for other in sibling_frames.get(sibling.pk) or [None]:
                if other is None:
                    errors.append(
                        f"{sibling.time_frame_label()} has no time frame, so it is "
                        f"active at all times on all timelines."
                    )
                elif self.shares_timeline_with(other) and self.overlaps(other):
                    errors.append(
                        f"Overlaps with {sibling.time_frame_label()} "
                        f"{other.format_interval()} on "
                        f"{self.format_timelines(other, user_timeline_labels)}."
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
