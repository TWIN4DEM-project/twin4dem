from typing import cast
from rest_framework import serializers

from common.fields import SeparatedValuesField
from common.models import Judge, PartyPositionType, SimulationInstitution
from api import fields
from ._base import LCCModelSerializer


class JudgeNetworkSerializer(LCCModelSerializer):
    neighbours_in = serializers.SerializerMethodField()
    neighbours_out = serializers.SerializerMethodField()
    party_label = serializers.SerializerMethodField()
    party_position = serializers.SerializerMethodField()
    weights = fields.SeparatedValuesSerializerField(
        model_field=cast(SeparatedValuesField, Judge._meta.get_field("weights"))
    )

    class Meta:
        model = Judge
        fields = [
            "id",
            "label",
            "is_president",
            "party_label",
            "party_position",
            "influence",
            "weights",
            "neighbours_in",
            "neighbours_out",
        ]

    def get_neighbours_out(self, obj):
        return list(obj.neighbours_out.values_list("id", flat=True))

    def get_neighbours_in(self, obj):
        return list(obj.neighbours_in.values_list("id", flat=True))

    def get_party_label(self, obj):
        return obj.party.label

    def get_party_position(self, obj):
        latest = obj.party.latest_position
        if latest is None:
            return PartyPositionType.INDEPENDENT
        return latest.position


class CourtSerializer(LCCModelSerializer):
    label = serializers.SerializerMethodField()
    probability_for = serializers.SerializerMethodField()
    judges = serializers.SerializerMethodField()

    class Meta:
        model = SimulationInstitution
        fields = ["id", "label", "probability_for", "judges"]

    def get_label(self, seat: SimulationInstitution):
        return seat.institution.label

    def get_probability_for(self, seat: SimulationInstitution):
        return seat.institution.get_payload().probability_for

    def get_judges(self, seat: SimulationInstitution):
        qs = seat.judges.all().prefetch_related("party")
        return JudgeNetworkSerializer(qs, many=True).data
