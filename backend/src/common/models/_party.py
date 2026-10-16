from typing import TYPE_CHECKING

from django.db import models
from django.db.models import F, OuterRef, Subquery

from common.models._settings import Country
from common.models._timeframe import TimeFrame, TimeFrameSubjectType

if TYPE_CHECKING:
    from common.models._party_position import PartyPosition


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
        newest_end = (
            TimeFrame.objects.filter(
                subject_type=TimeFrameSubjectType.PARTY_POSITION,
                subject_id=OuterRef("pk"),
            )
            .order_by(F("valid_to").desc(nulls_first=True))
            .values("valid_to")[:1]
        )
        return (
            self.positions.annotate(newest_end=Subquery(newest_end))
            .order_by(F("newest_end").desc(nulls_first=True), "-pk")
            .first()
        )

    class Meta:
        verbose_name_plural = "Parties"
        constraints = [
            models.UniqueConstraint(
                name="uq_party_country_label", fields=["country", "label"]
            )
        ]
