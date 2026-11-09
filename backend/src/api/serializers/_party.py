from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple

from django.db import models
from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from common.models import Party, PartyPosition, TimeFrame, TimeFrameSubjectType

from ._base import LCCModelSerializer
from ._institution import AllowedCountryField


class PositionSummary(NamedTuple):
    latest: PartyPosition | None
    active: PartyPosition | None


def _newest(
    positions: list[PartyPosition], ends: dict[int, list[datetime | None]]
) -> PartyPosition | None:
    """
    Takes a list of positions and returns the one that ends last.
    """

    def rank(position: PartyPosition) -> tuple:
        own_ends = ends[position.pk]
        end = None if not own_ends or None in own_ends else max(own_ends)
        return end is None, end, position.pk

    return max(positions, key=rank, default=None)


def position_summaries(
    parties: Sequence[Party], at: datetime
) -> dict[int, PositionSummary]:
    """
    Find the latest and the active position of each party.
    """
    positions = list(
        PartyPosition.objects.filter(party_id__in=[party.pk for party in parties])
    )
    ends = defaultdict(list)
    covering_ends = defaultdict(list)
    for subject_id, valid_from, valid_to in TimeFrame.objects.filter(
        subject_type=TimeFrameSubjectType.PARTY_POSITION,
        subject_id__in=[position.pk for position in positions],
    ).values_list("subject_id", "valid_from", "valid_to"):
        ends[subject_id].append(valid_to)
        if (valid_from is None or valid_from <= at) and (
            valid_to is None or at < valid_to
        ):
            covering_ends[subject_id].append(valid_to)

    by_party = defaultdict(list)
    for position in positions:
        by_party[position.party_id].append(position)

    summaries = {}
    for party in parties:
        own = by_party[party.pk]
        active = [p for p in own if not ends[p.pk] or covering_ends[p.pk]]
        summaries[party.pk] = PositionSummary(
            latest=_newest(own, ends), active=_newest(active, covering_ends)
        )
    return summaries


class PartyListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        """Find the positions of all the parties at once, for their children."""
        parties = list(
            data.all() if isinstance(data, models.manager.BaseManager) else data
        )
        self.summaries = position_summaries(parties, timezone.now())
        return super().to_representation(parties)


class PartySerializer(LCCModelSerializer):
    country = AllowedCountryField()

    class Meta:
        model = Party
        fields = ["id", "country", "label"]
        list_serializer_class = PartyListSerializer
        validators = [
            UniqueTogetherValidator(
                queryset=Party.objects.all(),
                fields=["country", "label"],
                message="A party with this label already exists in this country.",
            )
        ]

    def validate_country(self, value):
        if self.instance is not None and value != self.instance.country:
            raise serializers.ValidationError(
                "A party cannot be moved to another country."
            )
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        summaries = getattr(self.parent, "summaries", None)
        if summaries is None:
            summaries = position_summaries([instance], timezone.now())
        latest, active = summaries[instance.pk]
        data["latestPosition"] = latest.position if latest else None
        data["activePosition"] = active.position if active else None
        return data
