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


class InstitutionKindSerializer(LCCModelSerializer):
    name = serializers.CharField(source="institution_name", max_length=100)
    country = AllowedCountryField()
    institutions = InstitutionSerializer(many=True, required=False)

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
        institution_serializer = self.fields["institutions"].child
        for index, data in enumerate(institutions):
            try:
                institution_serializer.create({**data, "kind": kind})
            except serializers.ValidationError as e:
                # raised inside the atomic block: the kind is rolled back too
                raise serializers.ValidationError({"institutions": {index: e.detail}})
        return kind
