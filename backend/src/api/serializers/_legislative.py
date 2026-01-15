from typing import cast
from rest_framework import serializers

from common.fields import SeparatedValuesField
from common.models import Parliament, MemberOfParliament
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
        return obj.party.position


class ParliamentSerializer(LCCModelSerializer):
    members = serializers.SerializerMethodField()

    class Meta:
        model = Parliament
        fields = [
            "id",
            "label",
            "majority_probability_for",
            "opposition_probability_for",
            "members",
        ]

    def get_members(self, parliament):
        qs = parliament.members.all().prefetch_related("party")
        return MemberOfParliamentSerializer(qs, many=True).data
