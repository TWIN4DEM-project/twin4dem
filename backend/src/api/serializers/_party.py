from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple

from django.db import models, transaction
from django.db.models import F, FilteredRelation, Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from common.models import (
    FrameSpec,
    Party,
    PartyPosition,
    TimeFrame,
    TimeFrameSubjectType,
    VirtualTimeline,
)

from ._base import LCCModelSerializer
from ._institution import AllowedCountryField
from ._party_position import BasePartyPositionSerializer


class PositionSummary(NamedTuple):
    latest: PartyPosition
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
    parties: Sequence[Party],
    at: datetime,
    timeline: VirtualTimeline | None = None,
) -> dict[int, PositionSummary]:
    """
    Find the latest and the active position of each party.
    """
    positions = PartyPosition.objects.filter(
        party_id__in=[party.pk for party in parties]
    )
    if timeline is None:
        positions = positions.annotate(
            context_default=FilteredRelation(
                "party__country__user_settings__timelines",
                condition=Q(
                    party__country__user_settings__timelines__label=(
                        VirtualTimeline.DEFAULT_LABEL
                    )
                ),
            ),
            default_timeline_id=F("context_default__id"),
        )
    positions = list(positions)
    timeline_ids = {
        p.pk: timeline.pk if timeline is not None else p.default_timeline_id
        for p in positions
    }

    frames = {}
    links = defaultdict(set)
    for frame_id, subject_id, valid_from, valid_to, link in TimeFrame.objects.filter(
        subject_type=TimeFrameSubjectType.PARTY_POSITION,
        subject_id__in=[position.pk for position in positions],
    ).values_list(
        "id",
        "subject_id",
        "valid_from",
        "valid_to",
        "timeline_links__virtual_timeline_id",
    ):
        frames[frame_id] = subject_id, valid_from, valid_to
        if link is not None:
            links[frame_id].add(link)

    framed = set()
    ends = defaultdict(list)
    covering_ends = defaultdict(list)
    for frame_id, (subject_id, valid_from, valid_to) in frames.items():
        framed.add(subject_id)
        spec = FrameSpec(valid_from, valid_to, frozenset(links[frame_id]) or None)
        timeline_id = timeline_ids[subject_id]
        if spec.timeline_ids is not None and timeline_id not in spec.timeline_ids:
            continue
        ends[subject_id].append(valid_to)
        if spec.contains(timeline_id, at):
            covering_ends[subject_id].append(valid_to)

    positions.sort(key=lambda p: (p.chamber_id is None, p.chamber_id or 0))
    by_chamber = defaultdict(dict)
    for position in positions:
        by_chamber[position.party_id].setdefault(position.chamber_id, []).append(
            position
        )

    summaries = {}
    for party in parties:
        summaries[party.pk] = {}
        for chamber_id, own in by_chamber[party.pk].items():
            on_timeline = [p for p in own if p.pk not in framed or ends[p.pk]]
            if not on_timeline:
                continue
            active = [
                p for p in on_timeline if p.pk not in framed or covering_ends[p.pk]
            ]
            summaries[party.pk][chamber_id] = PositionSummary(
                latest=_newest(on_timeline, ends),
                active=_newest(active, covering_ends),
            )
    return summaries


class PartyListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        """Find the positions of all the parties at once, for their children."""
        parties = list(
            data.all() if isinstance(data, models.manager.BaseManager) else data
        )
        self.summaries = position_summaries(
            parties, timezone.now(), self.context.get("timeline")
        )
        return super().to_representation(parties)


class PartySerializer(LCCModelSerializer):
    country = AllowedCountryField()
    positions = BasePartyPositionSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Party
        fields = ["id", "country", "label", "positions"]
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

    def validate(self, attrs):
        if self.instance is not None and "positions" in attrs:
            raise serializers.ValidationError(
                {
                    "positions": (
                        "Positions can only be created together with their party."
                    )
                }
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        positions = validated_data.pop("positions", [])
        party = super().create(validated_data)
        try:
            self.fields["positions"].create(
                [{**data, "party": party} for data in positions]
            )
        except serializers.ValidationError as e:
            # raised inside the atomic block: the party is rolled back too
            raise serializers.ValidationError({"positions": e.detail})
        return party

    def to_representation(self, instance):
        data = super().to_representation(instance)
        summaries = getattr(self.parent, "summaries", None)
        if summaries is None:
            summaries = position_summaries(
                [instance], timezone.now(), self.context.get("timeline")
            )
        chambers = summaries[instance.pk].items()
        data["latestPositions"] = [
            {"chamber": chamber_id, "position": summary.latest.position}
            for chamber_id, summary in chambers
        ]
        data["activePositions"] = [
            {"chamber": chamber_id, "position": summary.active.position}
            for chamber_id, summary in chambers
            if summary.active is not None
        ]
        return data
