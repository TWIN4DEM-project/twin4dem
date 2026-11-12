from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple

from django.db import models, transaction
from django.db.models import F, FilteredRelation, Q, Value
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


def position_summaries(
    parties: Sequence[Party],
    at: datetime,
    timeline: VirtualTimeline | None = None,
) -> dict[int, dict[int | None, PositionSummary]]:
    """
    Find the latest and the active position of each party in each chamber, on a
    timeline.
    """
    positions = _positions_with_timeline(parties, timeline)
    frames = _frames_by_position(positions)
    summaries = {party.pk: {} for party in parties}
    for (party_id, chamber_id), chamber_positions in _by_chamber(positions).items():
        summary = _summarize(chamber_positions, frames, at)
        if summary is not None:
            summaries[party_id][chamber_id] = summary
    return summaries


def _positions_with_timeline(
    parties: Sequence[Party], timeline: VirtualTimeline | None
) -> list[PartyPosition]:
    """
    The positions of the parties, each annotated with `reported_timeline_id`:
    the given timeline, or else the default timeline of the party's global
    context (None if the context has none).
    """
    positions = PartyPosition.objects.filter(
        party_id__in=[party.pk for party in parties]
    )
    if timeline is not None:
        return list(positions.annotate(reported_timeline_id=Value(timeline.pk)))
    return list(
        positions.annotate(
            context_default=FilteredRelation(
                "party__country__user_settings__timelines",
                condition=Q(
                    party__country__user_settings__timelines__label=(
                        VirtualTimeline.DEFAULT_LABEL
                    )
                ),
            ),
            reported_timeline_id=F("context_default__id"),
        )
    )


def _frames_by_position(positions: list[PartyPosition]) -> dict[int, list[FrameSpec]]:
    """The time frames of the positions, with their timelines, by position id."""
    rows = TimeFrame.objects.filter(
        subject_type=TimeFrameSubjectType.PARTY_POSITION,
        subject_id__in=[position.pk for position in positions],
    ).values_list(
        "id",
        "subject_id",
        "valid_from",
        "valid_to",
        "timeline_links__virtual_timeline_id",
    )
    frames = {}
    links = defaultdict(set)
    for frame_id, subject_id, valid_from, valid_to, link in rows:
        frames[frame_id] = subject_id, valid_from, valid_to
        if link is not None:
            links[frame_id].add(link)

    by_position = defaultdict(list)
    for frame_id, (subject_id, valid_from, valid_to) in frames.items():
        by_position[subject_id].append(
            FrameSpec(valid_from, valid_to, frozenset(links[frame_id]) or None)
        )
    return by_position


def _by_chamber(
    positions: list[PartyPosition],
) -> dict[tuple[int, int | None], list[PartyPosition]]:
    """
    The positions grouped by party and chamber: the chambers in id order, the
    positions without a chamber last.
    """
    groups = defaultdict(list)
    for position in sorted(
        positions, key=lambda p: (p.chamber_id is None, p.chamber_id or 0)
    ):
        groups[position.party_id, position.chamber_id].append(position)
    return groups


def _summarize(
    positions: list[PartyPosition], frames: dict[int, list[FrameSpec]], at: datetime
) -> PositionSummary | None:
    """
    The latest and the active of the positions of one chamber, or None if none
    of them exists on its timeline.
    """
    on_timeline = {}
    covering = {}
    for position in positions:
        own = _frames_on_timeline(position, frames)
        if own:
            on_timeline[position] = own
            timeline_id = position.reported_timeline_id
            covering[position] = [f for f in own if f.contains(timeline_id, at)]
    if not on_timeline:
        return None
    return PositionSummary(
        latest=_newest(on_timeline),
        active=_newest({p: f for p, f in covering.items() if f}),
    )


def _frames_on_timeline(
    position: PartyPosition, frames: dict[int, list[FrameSpec]]
) -> list[FrameSpec]:
    """
    The frames of the position that count on its timeline: those without
    timeline links (all timelines) or with a link to it, the rule of
    `is_active`. A position without time frames is always there.
    """
    always = FrameSpec(valid_from=None, valid_to=None, timeline_ids=None)
    timeline_id = position.reported_timeline_id
    return [
        frame
        for frame in frames.get(position.pk) or [always]
        if frame.timeline_ids is None or timeline_id in frame.timeline_ids
    ]


def _newest(
    frames: dict[PartyPosition, list[FrameSpec]],
) -> PartyPosition | None:
    """
    Takes a list of positions and returns the one that ends last.
    """

    def rank(position: PartyPosition) -> tuple:
        ends = [frame.valid_to for frame in frames[position]]
        if None in ends:
            return True, None, position.pk
        return False, max(ends), position.pk

    return max(frames, key=rank, default=None)


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
