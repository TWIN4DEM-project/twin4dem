from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from common.models import Country, InstitutionKind

from ._base import LCCModelSerializer
from ._institution import InstitutionSerializer


class AllowedCountryField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        user = self.context["request"].user
        if user.is_superuser:
            return Country.objects.all()
        return Country.objects.filter(user_settings__user=user)


class KindInstitutionSerializer(InstitutionSerializer):

    class Meta(InstitutionSerializer.Meta):
        fields = ["id", "label", "size", "payload", "time_frames"]
        validators = []


class InstitutionKindSerializer(LCCModelSerializer):
    name = serializers.CharField(source="institution_name", max_length=100)
    country = AllowedCountryField()
    institutions = KindInstitutionSerializer(many=True, required=False)

    class Meta:
        model = InstitutionKind
        fields = ["id", "name", "country", "branch", "institutions"]
        validators = [
            UniqueTogetherValidator(
                queryset=InstitutionKind.objects.all(),
                fields=["country", "name"],
                message=(
                    "An institution kind with this name already exists in this "
                    "country."
                ),
            )
        ]

    def validate_country(self, value):
        if self.instance is not None and value != self.instance.country:
            raise serializers.ValidationError(
                "An institution kind cannot be moved to another country."
            )
        return value

    def validate_branch(self, value):
        if self.instance is not None and value != self.instance.branch:
            raise serializers.ValidationError(
                "The branch of an institution kind cannot be changed."
            )
        return value

    def validate(self, attrs):
        if self.instance is not None and "institutions" in attrs:
            raise serializers.ValidationError(
                {
                    "institutions": (
                        "Institutions can only be created together with their kind."
                    )
                }
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        institutions = validated_data.pop("institutions", [])
        kind = super().create(validated_data)
        try:
            self.fields["institutions"].create(
                [{**data, "kind": kind} for data in institutions]
            )
        except serializers.ValidationError as e:
            # raised inside the atomic block: the kind is rolled back too
            raise serializers.ValidationError({"institutions": e.detail})
        return kind
