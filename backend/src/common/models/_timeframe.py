from django.core.exceptions import ValidationError
from django.db import models
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


class TimeFrameQuerySet(models.QuerySet):
    def of(self, subject: TimeFrameSubject) -> "TimeFrameQuerySet":
        return self.filter(subject_type=subject_type_of(subject), subject_id=subject.pk)

    def create_for(self, subject: TimeFrameSubject, **kwargs) -> "TimeFrame":
        return self.create(
            subject_type=subject_type_of(subject), subject_id=subject.pk, **kwargs
        )


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

    def __str__(self):
        start = self.valid_from.isoformat() if self.valid_from else "-inf"
        end = self.valid_to.isoformat() if self.valid_to else "+inf"
        return f"{self.subject_type}={self.subject_id} [{start}, {end})"

    @property
    def subject(self) -> TimeFrameSubject | None:
        """The referenced subject, or None if it does not exist (anymore)."""
        model = SUBJECT_MODELS.get(self.subject_type)
        if model is None:
            return None
        return model.objects.filter(pk=self.subject_id).first()

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
        if self.subject_type in SUBJECT_MODELS and self.subject is None:
            raise ValidationError(
                {
                    "subject_id": (
                        f"There is no {self.subject_type} with id {self.subject_id}."
                    )
                }
            )

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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="uq_timelinetimeframe_time_frame_virtual_timeline",
                fields=["time_frame", "virtual_timeline"],
            )
        ]
