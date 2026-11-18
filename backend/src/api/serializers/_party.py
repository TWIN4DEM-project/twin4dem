from django.db import transaction
from django.db.models import F, OuterRef, Prefetch, Subquery
from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from common.models import Party, PartyPosition, PartyPositionTimeFrame, VirtualTimeline

from ._base import LCCModelSerializer
from ._institution import AllowedCountryField
from ._party_position import BasePartyPositionSerializer

ALL_TIMELINES = "*"


class PartyPositionSummaries:
    """The querysets behind the `latest_positions`/`active_positions` prefetches.

    `latest` is the most recent position per party, chamber and timeline;
    `active` the one covering `at` on each of those. Both are flat querysets,
    so a list of parties costs two constant queries however many parties it has.
    """

    @staticmethod
    def _with_timeline(positions):
        return positions.annotate(
            summary_timeline_id=Subquery(
                PartyPositionTimeFrame.objects.filter(subject=OuterRef("pk"))
                .order_by("timelines__id")
                .values("timelines__id")[:1]
            )
        ).order_by(F("chamber_id").asc(nulls_last=True), "summary_timeline_id", "pk")

    @classmethod
    def latest(cls, timeline: VirtualTimeline | None = None):
        return cls._with_timeline(
            PartyPosition.objects.most_recent(timeline, per_timeline=True)
        ).select_related("chamber")

    @classmethod
    def active(cls, at, timeline: VirtualTimeline | None = None):
        return cls._with_timeline(
            PartyPosition.objects.active_on(timeline, at).most_recent(
                timeline, per_timeline=True
            )
        ).select_related("chamber")

    @classmethod
    def prefetch(cls, parties, timeline: VirtualTimeline | None = None, at=None):
        """A parties queryset with latest_positions/active_positions prefetched."""
        if at is None:
            at = timezone.now()
        return parties.prefetch_related(
            Prefetch(
                "positions",
                queryset=cls.latest(timeline),
                to_attr="latest_positions",
            ),
            Prefetch(
                "positions",
                queryset=cls.active(at, timeline),
                to_attr="active_positions",
            ),
        )


class PositionSummaryListField(serializers.Field):
    """Renders a prefetched list of positions as flat summary entries.

    Each entry carries the timeline and the chamber of the position, with
    "*" for a position that applies to all timelines or all chambers.
    """

    def __init__(self, *, attr: str, **kwargs):
        self.attr = attr
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def get_attribute(self, instance):
        return getattr(instance, self.attr, [])

    def to_representation(self, value):
        return [
            {
                "timeline": position.summary_timeline_id or ALL_TIMELINES,
                "chamber": position.chamber_id or ALL_TIMELINES,
                "position": position.position,
            }
            for position in value
        ]


class PartyListSerializer(LCCModelSerializer):
    """A party in a list, with its latest and active positions per chamber and timeline."""

    country = AllowedCountryField(read_only=True)
    latest_positions = PositionSummaryListField(attr="latest_positions")
    active_positions = PositionSummaryListField(attr="active_positions")

    class Meta:
        model = Party
        fields = ["id", "country", "label", "latest_positions", "active_positions"]


class PartySerializer(LCCModelSerializer):
    country = AllowedCountryField()
    positions = BasePartyPositionSerializer(many=True, required=False, write_only=True)
    latest_positions = PositionSummaryListField(attr="latest_positions")
    active_positions = PositionSummaryListField(attr="active_positions")

    class Meta:
        model = Party
        fields = [
            "id",
            "country",
            "label",
            "positions",
            "latest_positions",
            "active_positions",
        ]
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
        timeline = self.context.get("timeline")
        if not hasattr(instance, "latest_positions"):
            instance.latest_positions = list(
                PartyPositionSummaries.latest(timeline).filter(party=instance)
            )
        if not hasattr(instance, "active_positions"):
            instance.active_positions = list(
                PartyPositionSummaries.active(timezone.now(), timeline).filter(
                    party=instance
                )
            )
        return super().to_representation(instance)
