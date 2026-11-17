from typing import TYPE_CHECKING

from django.db import models
from django.db.models import (
    Case,
    Count,
    DateTimeField,
    F,
    IntegerField,
    Max,
    Q,
    Value,
    When,
)

from ..world import Country

if TYPE_CHECKING:
    from ._party_position import PartyPosition


class Party(models.Model):
    """A political party of a country; available across all timelines."""

    id = models.AutoField(primary_key=True)
    country = models.ForeignKey(
        to=Country, on_delete=models.CASCADE, related_name="parties"
    )
    label = models.CharField(max_length=50)

    def __str__(self):
        return self.label

    @property
    def latest_position(self) -> "PartyPosition | None":
        """
        The most recent position, i.e. the one whose time frame has the
        greatest `valid_to`. A frame without `valid_to` is still active and
        ranks highest; a position without frames counts as active.
        """
        positions = self.positions.annotate(
            frame_count=Count("time_frames"),
            open_frame_count=Count(
                "time_frames", filter=Q(time_frames__valid_to__isnull=True)
            ),
            newest_end=Max("time_frames__valid_to"),
        ).annotate(
            is_current=Case(
                When(Q(frame_count=0) | Q(open_frame_count__gt=0), then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            latest_end=Case(
                When(open_frame_count__gt=0, then=Value(None)),
                default=F("newest_end"),
                output_field=DateTimeField(),
            ),
        )
        return positions.order_by(
            "is_current", F("latest_end").desc(nulls_first=True), "-pk"
        ).first()

    class Meta:
        verbose_name_plural = "Parties"
        constraints = [
            models.UniqueConstraint(
                name="uq_party_country_label", fields=["country", "label"]
            )
        ]
