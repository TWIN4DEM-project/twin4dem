from collections.abc import Iterable
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q

from ._spec import FrameSpec, _format_interval
from ._subjects import (
    TimeFrameMixin,
    TimeFrameSubjectType,
    _subject_models,
    subject_type_of,
)
from ._timeline import VirtualTimeline


class TimeFrameQuerySet(models.QuerySet):
    def of(self, subject: TimeFrameMixin) -> "TimeFrameQuerySet":
        return self.filter(subject_type=subject_type_of(subject), subject_id=subject.pk)

    def create_for(self, subject: TimeFrameMixin, **kwargs) -> "TimeFrame":
        """Create a time frame for the subject, without validation."""
        return self.create(
            subject_type=subject_type_of(subject), subject_id=subject.pk, **kwargs
        )

    def occupy(
        self,
        subject: TimeFrameMixin,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        timelines: Iterable[VirtualTimeline] = (),
    ) -> "TimeFrame":
        """
        Validate and create a time frame for the subject, restricted to the given
        timelines (no timelines: all timelines).
        """
        timelines = list(timelines)
        frame = self.model(
            subject_type=subject_type_of(subject),
            subject_id=subject.pk,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        frame.pending_timeline_ids = [t.pk for t in timelines] or None
        with transaction.atomic():
            frame.full_clean()
            frame.save()
            frame.timelines.set(timelines)
        return frame


class TimeFrame(models.Model):
    """An interval ``[valid_from, valid_to)`` in which a subject supporting
     time frames is active.

    A missing bound means the interval is open-ended. The subject is referenced
    through a soft foreign key:

    * ``subject_type`` represents the tag registered by the model supporting time frames
    * ``subject_id`` represents the primary key of the model instance

    There is no enforcement for soft foreign keys at the database level.
    A time frame without timeline links applies to all timelines of the
    subject's global context, including timelines added later.
    """

    id = models.AutoField(primary_key=True)
    subject_type = models.CharField(choices=TimeFrameSubjectType.choices, max_length=32)
    subject_id = models.IntegerField()
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    timelines = models.ManyToManyField(
        to=VirtualTimeline,
        through="TimelineTimeFrame",
        related_name="time_frames",
        blank=True,
    )

    objects = TimeFrameQuerySet.as_manager()

    # timelines to validate against instead of the stored links (empty: all
    # timelines); set before full_clean() when links are saved together with
    # the frame
    pending_timeline_ids: list[int] | None = None

    def __str__(self):
        return f"{self.subject_type}={self.subject_id} {_format_interval(self.spec)}"

    @property
    def subject(self) -> TimeFrameMixin | None:
        """The referenced subject, or None if it does not exist (anymore)."""
        model = _subject_models().get(self.subject_type)
        if model is None:
            return None
        return model.objects.filter(pk=self.subject_id).first()

    @property
    def spec(self) -> FrameSpec:
        timeline_ids = (
            frozenset(link.virtual_timeline_id for link in self.timeline_links.all())
            if self.pk is not None
            else frozenset()
        )
        return FrameSpec(self.valid_from, self.valid_to, timeline_ids or None)

    @property
    def is_on_all_timelines(self) -> bool:
        return not self.timeline_links.exists()

    def get_timelines(self) -> models.QuerySet[VirtualTimeline]:
        """The timelines this time frame is active on."""
        if self.is_on_all_timelines:
            subject = self.subject
            if subject is None:
                return VirtualTimeline.objects.none()
            return VirtualTimeline.objects.filter(
                user_settings_id=subject.time_frame_user_settings_id()
            )
        return self.timelines.all()

    def clean(self):
        super().clean()
        if self.subject_type not in _subject_models():
            return
        subject = self.subject
        if subject is None:
            raise ValidationError(
                {
                    "subject_id": (
                        f"There is no {self.subject_type} with id {self.subject_id}."
                    )
                }
            )

        if self.pending_timeline_ids is not None:
            timeline_ids = self.pending_timeline_ids
        else:
            timeline_ids = self.spec.timeline_ids
        # imported here: _validation depends on this module
        from ._validation import validate_time_frame

        validate_time_frame(subject, self, timeline_ids)

    class Meta:
        indexes = [
            models.Index(
                name="ix_timeframe_subject", fields=["subject_type", "subject_id"]
            )
        ]
        constraints = [
            models.CheckConstraint(
                name="ck_timeframe_subject_type",
                condition=Q(subject_type__in=TimeFrameSubjectType.values),
            ),
            models.CheckConstraint(
                name="ck_timeframe_valid_from_before_valid_to",
                condition=Q(valid_from__isnull=True)
                | Q(valid_to__isnull=True)
                | Q(valid_from__lt=F("valid_to")),
            ),
        ]


class TimelineTimeFrame(models.Model):
    """Restricts a time frame to a virtual timeline."""

    id = models.AutoField(primary_key=True)
    time_frame = models.ForeignKey(
        to=TimeFrame, on_delete=models.CASCADE, related_name="timeline_links"
    )
    virtual_timeline = models.ForeignKey(
        to=VirtualTimeline, on_delete=models.CASCADE, related_name="time_frame_links"
    )

    def clean(self):
        super().clean()
        subject = self.time_frame.subject
        if subject is None:
            return
        if (
            self.virtual_timeline.user_settings_id
            != subject.time_frame_user_settings_id()
        ):
            raise ValidationError(
                {
                    "virtual_timeline": (
                        "The timeline must belong to the same global context "
                        "as the time frame's subject."
                    )
                }
            )

        other_links = self.time_frame.timeline_links.exclude(pk=self.pk)
        timeline_ids = {
            self.virtual_timeline_id,
            *other_links.values_list("virtual_timeline_id", flat=True),
        }
        # imported here: _validation depends on this module
        from ._validation import validate_time_frame

        try:
            validate_time_frame(subject, self.time_frame, timeline_ids)
        except ValidationError as e:
            raise ValidationError({"virtual_timeline": e.messages})

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="uq_timelinetimeframe_time_frame_virtual_timeline",
                fields=["time_frame", "virtual_timeline"],
            )
        ]
