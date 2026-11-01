from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.settings import api_settings

from common.models import Institution, Party, PartyPosition, TimeFrame

from ._base import LCCModelSerializer
from ._institution import AllowedTimelineField


class AllowedPartyField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        user = self.context["request"].user
        if user.is_superuser:
            return Party.objects.all()
        return Party.objects.filter(country__user_settings__user=user)


class AllowedChamberField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        user = self.context["request"].user
        if user.is_superuser:
            return Institution.objects.all()
        return Institution.objects.filter(kind__country__user_settings__user=user)


class PartyPositionListSerializer(serializers.ListSerializer):
    @transaction.atomic
    def create(self, validated_data):

        positions = []
        for index, attrs in enumerate(validated_data):
            try:
                positions.append(self.child.create(attrs))
            except serializers.ValidationError as e:
                errors = [{} for _ in validated_data]
                errors[index] = e.detail
                raise serializers.ValidationError(errors)
        return positions


class PartyPositionSerializer(LCCModelSerializer):
    party = AllowedPartyField()
    chamber = AllowedChamberField(allow_null=True, default=None)
    timeline = AllowedTimelineField(allow_null=True, default=None, write_only=True)
    valid_from = serializers.DateTimeField(
        allow_null=True, default=None, write_only=True
    )
    valid_to = serializers.DateTimeField(allow_null=True, default=None, write_only=True)

    class Meta:
        model = PartyPosition
        fields = [
            "id",
            "party",
            "position",
            "chamber",
            "timeline",
            "valid_from",
            "valid_to",
        ]
        list_serializer_class = PartyPositionListSerializer

    def validate_party(self, value):
        if self.instance is not None and value != self.instance.party:
            raise serializers.ValidationError(
                "A party position cannot be moved to another party."
            )
        return value

    def validate(self, attrs):
        valid_from, valid_to = attrs.get("valid_from"), attrs.get("valid_to")
        if valid_from is not None and valid_to is not None and valid_from >= valid_to:
            raise serializers.ValidationError(
                {"valid_to": "The time frame must end after it starts."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        frame = self._pop_time_frame(validated_data)
        position = PartyPosition(**validated_data)
        self._clean_and_save(position)
        self._occupy(position, frame)
        return position

    @transaction.atomic
    def update(self, instance, validated_data):
        frame = self._pop_time_frame(validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        self._clean_and_save(instance)
        TimeFrame.objects.of(instance).delete()
        self._occupy(instance, frame)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        frame = TimeFrame.objects.of(instance).order_by("id").first()
        timeline_id = valid_from = valid_to = None
        if frame is not None:
            timeline_id = (
                frame.timeline_links.order_by("id")
                .values_list("virtual_timeline_id", flat=True)
                .first()
            )
            valid_from, valid_to = frame.valid_from, frame.valid_to
        data["timeline"] = timeline_id
        data["validFrom"] = self.fields["valid_from"].to_representation(valid_from)
        data["validTo"] = self.fields["valid_to"].to_representation(valid_to)
        return data

    @staticmethod
    def _pop_time_frame(validated_data: dict) -> dict:
        timeline = validated_data.pop("timeline", None)
        return {
            "valid_from": validated_data.pop("valid_from", None),
            "valid_to": validated_data.pop("valid_to", None),
            "timelines": [timeline] if timeline is not None else [],
        }

    @staticmethod
    def _clean_and_save(position: PartyPosition):
        try:
            position.full_clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(serializers.as_serializer_error(e))
        position.save()

    @staticmethod
    def _occupy(position: PartyPosition, frame: dict):
        try:
            TimeFrame.objects.occupy(position, **frame)
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                {api_settings.NON_FIELD_ERRORS_KEY: e.messages}
            )
