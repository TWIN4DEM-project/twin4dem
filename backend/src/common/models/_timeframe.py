from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q

from common.models._institution import Institution
from common.models._party import PartyPosition
from common.models._settings import VirtualTimeline


class TimeFrameSubjectType(models.TextChoices):
    INSTITUTION = "institution"
    PARTY_POSITION = "party_position"


SUBJECT_MODELS: dict[str, type[models.Model]] = {
    TimeFrameSubjectType.INSTITUTION: Institution,
    TimeFrameSubjectType.PARTY_POSITION: PartyPosition,
}

type TimeFrameSubject = Institution | PartyPosition


def subject_type_of(subject: TimeFrameSubject) -> str:
    for subject_type, model in SUBJECT_MODELS.items():
        if isinstance(subject, model):
            return subject_type
    raise TypeError(f"{type(subject).__name__} cannot occupy a time frame")


def subject_user_settings_id(subject: TimeFrameSubject) -> int:
    if isinstance(subject, Institution):
        return subject.institution_taxonomy.country.user_settings_id
    return subject.party.country.user_settings_id


@dataclass(frozen=True)
class FrameSpec:
    """
    The interval [valid_from, valid_to) on a set of timelines. A missing bound is
    open-ended; `timeline_ids=None` stands for all timelines.
    """

    valid_from: datetime | None
    valid_to: datetime | None
    timeline_ids: frozenset[int] | None

    def overlaps_in_time(self, other: "FrameSpec") -> bool:
        starts_before_other_ends = (
            self.valid_from is None
            or other.valid_to is None
            or self.valid_from < other.valid_to
        )
        other_starts_before_end = (
            other.valid_from is None
            or self.valid_to is None
            or other.valid_from < self.valid_to
        )
        return starts_before_other_ends and other_starts_before_end

    def shared_timelines(self, other: "FrameSpec") -> frozenset[int] | None:
        """The timelines both frames are on (None: all timelines)."""
        if self.timeline_ids is None:
            return other.timeline_ids
        if other.timeline_ids is None:
            return self.timeline_ids
        return self.timeline_ids & other.timeline_ids

    def shares_timeline_with(self, other: "FrameSpec") -> bool:
        shared = self.shared_timelines(other)
        return shared is None or bool(shared)

    def contains(self, timeline_id: int, at: datetime) -> bool:
        """Whether the frame covers the point in time `at` on the timeline."""
        on_timeline = self.timeline_ids is None or timeline_id in self.timeline_ids
        started = self.valid_from is None or self.valid_from <= at
        not_ended = self.valid_to is None or at < self.valid_to
        return on_timeline and started and not_ended


# a subject without time frames is active at all times, on all timelines
ALWAYS = FrameSpec(valid_from=None, valid_to=None, timeline_ids=None)


class TimeFrameQuerySet(models.QuerySet):
    def of(self, subject: TimeFrameSubject) -> "TimeFrameQuerySet":
        return self.filter(subject_type=subject_type_of(subject), subject_id=subject.pk)

    def create_for(self, subject: TimeFrameSubject, **kwargs) -> "TimeFrame":
        """Create a time frame for the subject, without validation."""
        return self.create(
            subject_type=subject_type_of(subject), subject_id=subject.pk, **kwargs
        )

    def occupy(
        self,
        subject: TimeFrameSubject,
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
        frame.pending_timeline_ids = [t.pk for t in timelines]
        with transaction.atomic():
            frame.full_clean()
            frame.save()
            frame.timelines.set(timelines)
        return frame


class TimeFrame(models.Model):
    """
    The interval [valid_from, valid_to) in which a subject (an institution or a
    party position) is active. A missing bound means the interval is open-ended.

    The subject is referenced through a soft foreign key: `subject_type` names the
    model and `subject_id` its primary key. The database does not enforce it.

    A time frame without timeline links applies to all timelines of the subject's
    global context, including timelines added later.
    """

    id = models.AutoField(primary_key=True)
    subject_type = models.CharField(choices=TimeFrameSubjectType.choices)
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
    def subject(self) -> TimeFrameSubject | None:
        """The referenced subject, or None if it does not exist (anymore)."""
        model = SUBJECT_MODELS.get(self.subject_type)
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
    def applies_to_all_timelines(self) -> bool:
        return not self.timeline_links.exists()

    def get_timelines(self) -> models.QuerySet[VirtualTimeline]:
        """The timelines this time frame is active on."""
        if self.applies_to_all_timelines:
            subject = self.subject
            if subject is None:
                return VirtualTimeline.objects.none()
            return VirtualTimeline.objects.filter(
                user_settings_id=subject_user_settings_id(subject)
            )
        return self.timelines.all()

    def clean(self):
        super().clean()
        if self.subject_type not in SUBJECT_MODELS:
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
        if self.time_frame_id is None or self.virtual_timeline_id is None:
            return
        subject = self.time_frame.subject
        if subject is None:
            return
        if self.virtual_timeline.user_settings_id != subject_user_settings_id(subject):
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


# --- overlap rules --------------------------------------------------------------


def _siblings(subject: TimeFrameSubject) -> models.QuerySet:
    """
    The subjects that may not be active at the same time as `subject`: the other
    institutions of the same type, or the other positions of the same party in the
    same chamber.
    """
    if isinstance(subject, Institution):
        siblings = Institution.objects.filter(
            institution_taxonomy_id=subject.institution_taxonomy_id
        )
    else:
        siblings = PartyPosition.objects.filter(
            party_id=subject.party_id, chamber_id=subject.chamber_id
        ).select_related("party")
    return siblings.exclude(pk=subject.pk) if subject.pk is not None else siblings


def _label(subject: TimeFrameSubject) -> str:
    if isinstance(subject, Institution):
        return f"'{subject.label}'"
    return f"'{subject.party.label}' ({subject.position})"


def _format_bound(value: datetime | None, default: str) -> str:
    if value is None:
        return default
    is_midnight = (value.hour, value.minute, value.second, value.microsecond) == (
        0,
        0,
        0,
        0,
    )
    return value.date().isoformat() if is_midnight else value.isoformat()


def _format_interval(spec: FrameSpec) -> str:
    start = _format_bound(spec.valid_from, "-inf")
    end = _format_bound(spec.valid_to, "+inf")
    return f"[{start}, {end})"


def _format_timelines(timeline_ids: frozenset[int] | None, labels: dict) -> str:
    if timeline_ids is None:
        return "all timelines"
    names = sorted(f"'{labels.get(i, i)}'" for i in timeline_ids)
    return ("timeline " if len(names) == 1 else "timelines ") + ", ".join(names)


def frameless_sibling(subject: TimeFrameSubject) -> TimeFrameSubject | None:
    """
    A sibling without time frames, which is active at all times on all timelines
    and therefore leaves no room for `subject`.
    """
    siblings = _siblings(subject)
    with_frames = TimeFrame.objects.filter(
        subject_type=subject_type_of(subject), subject_id__in=siblings.values("pk")
    ).values("subject_id")
    return siblings.exclude(pk__in=with_frames).first()


def validate_time_frame(
    subject: TimeFrameSubject,
    frame: TimeFrame,
    timeline_ids: Iterable[int] | None,
) -> None:
    """
    Check that `subject` may occupy `frame` on the given timelines (none: all
    timelines):

    1. a subject occupies at most one time frame per timeline;
    2. its siblings (see `_siblings`) are not active at the same time on the same
       timeline. A sibling without time frames is always active.
    """
    candidate = FrameSpec(
        frame.valid_from, frame.valid_to, frozenset(timeline_ids or ()) or None
    )
    labels = dict(
        VirtualTimeline.objects.filter(
            user_settings_id=subject_user_settings_id(subject)
        ).values_list("id", "label")
    )

    if (
        candidate.timeline_ids is not None
        and not candidate.timeline_ids <= labels.keys()
    ):
        raise ValidationError(
            "The timelines must belong to the same global context as the "
            "time frame's subject."
        )

    errors = []

    own_frames = TimeFrame.objects.of(subject).prefetch_related("timeline_links")
    if frame.pk is not None:
        own_frames = own_frames.exclude(pk=frame.pk)
    for other in own_frames:
        if candidate.shares_timeline_with(other.spec):
            errors.append(
                f"{_label(subject)} already occupies the time frame "
                f"{_format_interval(other.spec)} on "
                f"{_format_timelines(candidate.shared_timelines(other.spec), labels)}."
            )

    siblings = list(_siblings(subject))
    sibling_frames = defaultdict(list)
    for sibling_frame in TimeFrame.objects.filter(
        subject_type=subject_type_of(subject),
        subject_id__in=[s.pk for s in siblings],
    ).prefetch_related("timeline_links"):
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
                    f"{_label(sibling)} has no time frame, so it is active at all "
                    f"times on all timelines."
                )
            else:
                errors.append(
                    f"Overlaps with {_label(sibling)} {_format_interval(spec)} on "
                    f"{_format_timelines(candidate.shared_timelines(spec), labels)}."
                )

    if errors:
        raise ValidationError(errors)


# --- queries --------------------------------------------------------------------


def active_subjects(
    subjects: Iterable[TimeFrameSubject], timeline: VirtualTimeline, at: datetime
) -> list[TimeFrameSubject]:
    """
    The subjects (all of the same type) active on `timeline` at the point in time
    `at`. A subject without time frames is always active.
    """
    subjects = list(subjects)
    if not subjects:
        return []
    frames = defaultdict(list)
    for frame in TimeFrame.objects.filter(
        subject_type=subject_type_of(subjects[0]),
        subject_id__in=[s.pk for s in subjects],
    ).prefetch_related("timeline_links"):
        frames[frame.subject_id].append(frame.spec)
    return [
        subject
        for subject in subjects
        if not frames[subject.pk]
        or any(spec.contains(timeline.pk, at) for spec in frames[subject.pk])
    ]


def is_active(
    subject: TimeFrameSubject, timeline: VirtualTimeline, at: datetime
) -> bool:
    return bool(active_subjects([subject], timeline, at))


def party_position_at(
    party, chamber: Institution, timeline: VirtualTimeline, at: datetime
) -> PartyPosition | None:
    """The position `party` holds in `chamber` on `timeline` at `at`, if any."""
    positions = active_subjects(
        PartyPosition.objects.filter(party=party, chamber=chamber), timeline, at
    )
    return positions[0] if positions else None
