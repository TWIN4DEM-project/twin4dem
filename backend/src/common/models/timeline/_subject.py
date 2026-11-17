from datetime import datetime
from functools import cached_property
from typing import NamedTuple

from django.db import models
from django.db.models import Q

from ._timeline import VirtualTimeline


class TimeFrameSubjectSiblings(NamedTuple):
    subject_type: type
    fields: tuple[str, ...]
    values: tuple[object, ...]

    def as_dict(self) -> dict:
        return dict(zip(self.fields, self.values))


class TimeFrameSubjectQuerySet(models.QuerySet):
    def active_on(
        self, timeline: VirtualTimeline, at: datetime
    ) -> "TimeFrameSubjectQuerySet":
        """The subjects active on the timeline at ``at``.

        A subject without time frames is active at all times on all timelines.
        """
        return self.filter(
            Q(time_frames__isnull=True)
            | (
                (
                    Q(time_frames__valid_from__isnull=True)
                    | Q(time_frames__valid_from__lte=at)
                )
                & (
                    Q(time_frames__valid_to__isnull=True)
                    | Q(time_frames__valid_to__gt=at)
                )
                & (
                    Q(time_frames__timelines=timeline)
                    | Q(time_frames__timelines__isnull=True)
                )
            )
        ).distinct()


class TimeFrameSubject(models.Model):
    """A model that can occupy time frames.

    Concrete subclasses declare in ``sibling_fields`` which axes make two
    subjects conflict, implement ``sibling_time_frames`` with the manager of a
    frame model defined next to them, and provide the user settings for their
    global context. The frame models supply the ``time_frames`` reverse
    relation, so subjects add no timeframe fields and require no timeframe
    migration.
    """

    objects = TimeFrameSubjectQuerySet.as_manager()

    sibling_fields: tuple[str, ...] = ()

    class Meta:
        abstract = True

    @property
    def time_frames(self) -> models.Manager:
        """The subject's time frames, supplied by the concrete frame model."""
        raise NotImplementedError

    @cached_property
    def sibling_values(self) -> TimeFrameSubjectSiblings:
        """The values that determine which subjects conflict with this one."""
        values = []
        for name in self.sibling_fields:
            id_name = f"{name}_id"
            if hasattr(self, id_name):
                values.append(getattr(self, id_name))
            else:
                values.append(getattr(self, name))
        return TimeFrameSubjectSiblings(type(self), self.sibling_fields, tuple(values))

    def siblings(self) -> models.QuerySet:
        """The subjects that may not be active at the same time as self."""
        if not self.sibling_fields:
            return type(self).objects.none()
        siblings = type(self).objects.filter(**self.sibling_values.as_dict())
        return siblings.exclude(pk=self.pk) if self.pk is not None else siblings

    def time_frame_label(self) -> str:
        """The subject's name in overlap error messages."""
        return f"'{self.label}'"

    def time_frame_user_settings_id(self) -> int:
        """The global context whose timelines the subject's frames apply to."""
        raise NotImplementedError

    def sibling_time_frames(self) -> models.QuerySet:
        """The time frames of this subject's siblings.

        Concrete subjects implement it with their frame model's manager.
        """
        raise NotImplementedError

    def frameless_sibling(self) -> "TimeFrameSubject | None":
        """A sibling without frames, which is active at all times."""
        siblings = self.siblings()
        with_frames = self.sibling_time_frames().values("subject_id")
        return siblings.exclude(pk__in=with_frames).first()

    def is_active(self, timeline: VirtualTimeline, at: datetime) -> bool:
        """Whether this subject is active on the timeline at ``at``."""
        return type(self).objects.active_on(timeline, at).filter(pk=self.pk).exists()
