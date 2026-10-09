from typing import cast
from rest_framework import serializers

from common.fields import SeparatedValuesField
from common.models import (
    MemberOfParliament,
    PartyPositionType,
    SimulationInstitution,
)
from api import fields
from ._base import LCCModelSerializer


class MemberOfParliamentSerializer(LCCModelSerializer):
    party_label = serializers.SerializerMethodField()
    party_position = serializers.SerializerMethodField()
    weights = fields.SeparatedValuesSerializerField(
        model_field=cast(
            SeparatedValuesField, MemberOfParliament._meta.get_field("weights")
        )
    )

    class Meta:
        model = MemberOfParliament
        fields = [
            "id",
            "label",
            "is_head",
            "party_label",
            "party_position",
            "weights",
        ]

    def get_party_label(self, obj):
        return obj.party.label

    def get_party_position(self, obj):
        latest = obj.party.latest_position
        if latest is None:
            return PartyPositionType.INDEPENDENT
        return latest.position


class ParliamentSerializer(LCCModelSerializer):
    label = serializers.SerializerMethodField()
    majority_probability_for = serializers.SerializerMethodField()
    opposition_probability_for = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()

    class Meta:
        model = SimulationInstitution
        fields = [
            "id",
            "label",
            "majority_probability_for",
            "opposition_probability_for",
            "members",
        ]

    def get_label(self, seat: SimulationInstitution):
        return seat.institution.label

    def get_majority_probability_for(self, seat: SimulationInstitution):
        return seat.institution.get_payload().majority_probability_for

    def get_opposition_probability_for(self, seat: SimulationInstitution):
        return seat.institution.get_payload().opposition_probability_for

    def get_members(self, seat: SimulationInstitution):
        qs = seat.members.all().prefetch_related("party")
        return MemberOfParliamentSerializer(qs, many=True).data
