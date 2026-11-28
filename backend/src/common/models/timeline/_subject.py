from datetime import datetime
from functools import cached_property
from typing import NamedTuple, Self

from django.db import models
from django.db.models import Q, OuterRef, Subquery, F, OrderBy, Window
from django.db.models.functions import RowNumber

from ._timeline import VirtualTimeline


class TimeFrameSubjectSiblings(NamedTuple):
    subject_type: type
    fields: tuple[str, ...]
    values: tuple[object, ...]

    def as_dict(self) -> dict:
        return dict(zip(self.fields, self.values))


class TimeFrameSubjectQuerySet(models.QuerySet):
    @staticmethod
    def _active_at_filter(at: datetime) -> Q:
        return (
            Q(time_frames__valid_from__isnull=True) | Q(time_frames__valid_from__lte=at)
        ) & (Q(time_frames__valid_to__isnull=True) | Q(time_frames__valid_to__gt=at))

    @staticmethod
    def _timeline_filter(timeline: VirtualTimeline) -> Q:
        return Q(time_frames__timelines=timeline) | Q(
            time_frames__timelines__isnull=True
        )

    @staticmethod
    def _order_by_recency() -> list[OrderBy]:
        return [F("most_recent").desc(nulls_first=True), F("pk").desc()]

    @classmethod
    def _active_filter(cls, timeline: VirtualTimeline | None, at: datetime | None) -> Q:
        q = Q()
        if at is not None:
            q &= cls._active_at_filter(at)
        if timeline is not None:
            q &= cls._timeline_filter(timeline)
        return q

    @property
    def _all_subjects(self) -> models.QuerySet["TimeFrameSubject"]:
        return self.model._base_manager.all()

    def _with_most_recent(self, timeline: VirtualTimeline | None) -> Self:
        """Annotate `latest_end`: NULL if any frame is open or there are no frames,
        otherwise the greatest valid_to."""
        own_time_frames = self._all_subjects.filter(pk=OuterRef("pk"))
        if timeline is not None:
            own_time_frames = own_time_frames.filter(self._timeline_filter(timeline))
        return self.annotate(
            most_recent=Subquery(
                own_time_frames.order_by(
                    F("time_frames__valid_to").desc(nulls_first=True)
                ).values("time_frames__valid_to")[:1]
            )
        )

    def active_on(self, timeline: VirtualTimeline | None, at: datetime) -> Self:
        """The subjects active on the timeline at ``at``.

        A subject without time frames is always active on all timelines.
        A ``None`` timeline matches frames on any timeline.
        """
        return self.filter(
            Q(time_frames__isnull=True) | self._active_filter(timeline, at)
        ).distinct()

    def by_recency(self, timeline: VirtualTimeline | None = None) -> Self:
        """All subjects, most recent first."""
        return self._with_most_recent(timeline).order_by(*self._order_by_recency())

    def most_recent(
        self,
        timeline: VirtualTimeline | None = None,
        per: tuple[str, ...] | None = None,
        *,
        per_timeline: bool = False,
    ) -> Self:
        """Keep only the most recent subject per group of siblings.

        Groups by ``model.sibling_fields`` unless ``per`` is given.
        An empty grouping keeps the single most recent subject overall.
        With ``per_timeline``, the frame's timeline link joins the grouping,
        keeping one subject per group per timeline; a subject whose frames
        have no timeline links forms the NULL-timeline group, i.e. the one
        applying to all timelines.
        """
        per = self.model.sibling_fields if per is None else per
        if per_timeline:
            per = per + ("time_frames__timelines",)
        queryset = self._with_most_recent(timeline)
        if timeline is not None:
            queryset = queryset.filter(
                Q(time_frames__isnull=True) | self._timeline_filter(timeline)
            )
        return queryset.annotate(
            recency_rank=Window(
                RowNumber(),
                partition_by=[F(field) for field in per] or None,
                order_by=self._order_by_recency(),
            )
        ).filter(recency_rank=1)


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
