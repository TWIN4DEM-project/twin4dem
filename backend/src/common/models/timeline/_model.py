from collections import defaultdict
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import F, Q

from ._subject import TimeFrameSubject
from ._query_set import TimeFrameQuerySet
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
    pending_timelines: list[VirtualTimeline] | None = None

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
        timelines = self._get_own_timelines()
        if timelines is None:
            return None
        return frozenset(x.pk for x in timelines)

    def _get_own_timelines(self) -> frozenset[VirtualTimeline] | None:
        if self.pending_timelines is not None:
            return frozenset(timeline for timeline in self.pending_timelines) or None
        if self.pk is None:
            return None
        return frozenset(timeline for timeline in self.timelines.all()) or None

    @property
    def is_on_all_timelines(self) -> bool:
        return self.timeline_ids is None

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

    def validate_time_frame(self) -> None:
        """Validate this frame of its subject on its timelines.

        A subject occupies at most one time frame per timeline. Its siblings
        may not be active at the same time on the same timeline. A sibling
        without time frames is active at all times on all timelines.
        """
        errors = []
        subj_frames = self._query_subject_time_frames()
        sibling_frames = list(
            self.subject.sibling_time_frames().prefetch_related("timelines")
        )
        labels = self._get_labels([*subj_frames, *sibling_frames])

        self._validate_subject_time_frames(errors, subj_frames, labels)
        self._validate_sibling_time_frames(errors, sibling_frames, labels)

        if errors:
            raise ValidationError(errors)

    def _query_subject_time_frames(self) -> list[Any]:
        own_subj_frames = type(self).objects.of(self.subject)
        if self.pk is not None:
            own_subj_frames = own_subj_frames.exclude(pk=self.pk)
        own_subj_frames = list(own_subj_frames.prefetch_related("timelines"))
        return own_subj_frames

    def _get_labels(self, others: list["TimeFrameModel"]) -> dict[int, str]:
        result: dict[int, str] = {}
        all_timelines = list(self._get_own_timelines() or ())
        all_timelines.extend(
            timeline
            for other in others
            for timeline in (other._get_own_timelines() or ())
        )
        for timeline in all_timelines:
            result[timeline.pk] = timeline.label
        return result

    def _validate_subject_time_frames(
        self, errors: list[Any], frames: list[Any], labels: dict[int, str]
    ):
        err_template = "{} already occupies the time frame {} on {}."
        for frame in frames:
            if not self.shares_timeline_with(frame):
                continue
            errors.append(
                err_template.format(
                    self.subject.time_frame_label(),
                    frame.format_interval(),
                    self.format_timelines(frame, labels),
                )
            )

    def _validate_sibling_time_frames(
        self, errors: list[Any], frames: list[Any], labels: dict[int, str]
    ):
        siblings = list(self.subject.siblings())
        time_frame_map = self._by_subject_id(frames)

        for s in siblings:
            s_frames = time_frame_map.get(s.pk, [])
            if len(s_frames) == 0:
                err = "{} is active at all times on all timelines.".format(
                    s.time_frame_label()
                )
                errors.append(err)
                continue

            for frame in s_frames:
                if not self.overlaps(frame):
                    continue
                err = "Overlaps with {} {} on {}.".format(
                    s.time_frame_label(),
                    frame.format_interval(),
                    self.format_timelines(frame, labels),
                )
                errors.append(err)

    @staticmethod
    def _by_subject_id(
        frames: list["TimeFrameModel"],
    ) -> dict[int, list["TimeFrameModel"]]:
        result = defaultdict(list)
        for frame in frames:
            result[frame.subject_id].append(frame)
        return result

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
