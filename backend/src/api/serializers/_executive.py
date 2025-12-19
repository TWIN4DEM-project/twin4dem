from typing import cast
from rest_framework import serializers

from common.fields import SeparatedValuesField
from common.models import Cabinet, Minister
from api import fields
from ._base import LCCModelSerializer


class MinisterNetworkSerializer(LCCModelSerializer):
    neighbours_in = serializers.SerializerMethodField()
    neighbours_out = serializers.SerializerMethodField()
    party_label = serializers.SerializerMethodField()
    weights = fields.SeparatedValuesSerializerField(
        model_field=cast(SeparatedValuesField, Minister._meta.get_field("weights"))
    )

    class Meta:
        model = Minister
        fields = [
            "id",
            "label",
            "is_prime_minister",
            "party_label",
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


class CabinetSerializer(LCCModelSerializer):
    ministers = serializers.SerializerMethodField()

    class Meta:
        model = Cabinet
        fields = [
            "id",
            "label",
            "government_probability_for",
            "legislative_probability",
            "ministers",
        ]

    def get_ministers(self, cabinet):
        qs = cabinet.ministers.all().prefetch_related(
            "party", "neighbours_out", "neighbours_in"
        )
        return MinisterNetworkSerializer(qs, many=True).data
