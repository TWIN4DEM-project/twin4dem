from django.core.exceptions import NON_FIELD_ERRORS
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.settings import api_settings
from rest_framework.validators import UniqueTogetherValidator

from common.models import (
    Country,
    Institution,
    InstitutionKind,
    TimeFrame,
    VirtualTimeline,
)

from ._base import LCCModelSerializer
from ._batch import BatchListSerializer


class AllowedCountryField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        user = self.context["request"].user
        if user.is_superuser:
            return Country.objects.all()
        return Country.objects.filter(user_settings__user=user)


class InstitutionCountryField(AllowedCountryField):
    def get_attribute(self, instance):
        return instance.kind.country


class AllowedInstitutionKindField(serializers.PrimaryKeyRelatedField):
    """
    The kinds supported by the `country` given next to the kind, for superusers
    too. The country goes through its own field, which limits it to the user's
    countries.
    """

    default_error_messages = {
        "does_not_exist": "The institution's country does not support this kind.",
    }

    def get_queryset(self):
        data = getattr(self.parent, "initial_data", {})
        try:
            country = self.parent.fields["country"].run_validation(data.get("country"))
        except serializers.ValidationError:
            return InstitutionKind.objects.none()
        return InstitutionKind.objects.filter(country=country)


class AllowedTimelineField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        user = self.context["request"].user
        if user.is_superuser:
            return VirtualTimeline.objects.all()
        return VirtualTimeline.objects.filter(user_settings__user=user)


class TimeFrameListSerializer(serializers.ListSerializer):
    def get_attribute(self, instance):
        return TimeFrame.objects.of(instance).order_by("id")


class TimeFrameSerializer(LCCModelSerializer):
    timelines = AllowedTimelineField(many=True, required=False)

    class Meta:
        model = TimeFrame
        fields = ["valid_from", "valid_to", "timelines"]
        list_serializer_class = TimeFrameListSerializer

    def validate(self, attrs):
        valid_from, valid_to = attrs.get("valid_from"), attrs.get("valid_to")
        if valid_from is not None and valid_to is not None and valid_from >= valid_to:
            raise serializers.ValidationError(
                {"valid_to": "The time frame must end after it starts."}
            )
        return attrs


class BaseInstitutionSerializer(LCCModelSerializer):
    payload = serializers.JSONField(default=dict)
    time_frames = TimeFrameSerializer(many=True, required=False)

    class Meta:
        model = Institution
        fields = ["id", "label", "size", "payload", "time_frames"]
        list_serializer_class = BatchListSerializer

    @transaction.atomic
    def create(self, validated_data):
        frames = validated_data.pop("time_frames", [])
        institution = Institution(**validated_data)
        self._clean(institution, frames)
        institution.save()
        self._occupy_time_frames(institution, frames)
        return institution

    @transaction.atomic
    def update(self, instance, validated_data):
        frames = validated_data.pop("time_frames", [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        self._clean(instance, frames)
        instance.save()
        TimeFrame.objects.of(instance).delete()
        self._occupy_time_frames(instance, frames)
        return instance

    @staticmethod
    def _clean(institution: Institution, frames: list[dict]):
        try:
            institution.full_clean()
        except DjangoValidationError as e:
            errors = serializers.as_serializer_error(e)
            if NON_FIELD_ERRORS in errors:
                errors[api_settings.NON_FIELD_ERRORS_KEY] = errors.pop(NON_FIELD_ERRORS)
            raise serializers.ValidationError(errors)

        if not frames and institution.time_frame_siblings().exists():
            raise serializers.ValidationError(
                {
                    "time_frames": [
                        "Without time frames the institution is active at all times, "
                        "so it would overlap the other institutions of the same kind."
                    ]
                }
            )

    def _occupy_time_frames(self, institution: Institution, frames: list[dict]):
        """Validate and create the time frames of the institution, one at a time."""

        errors = []
        for frame in frames:
            try:
                TimeFrame.objects.occupy(institution, **frame)
            except DjangoValidationError as e:
                errors.append({api_settings.NON_FIELD_ERRORS_KEY: e.messages})
            else:
                errors.append({})
        if any(errors):
            raise serializers.ValidationError({"time_frames": errors})


class InstitutionSerializer(BaseInstitutionSerializer):
    country = InstitutionCountryField()
    kind = AllowedInstitutionKindField()

    class Meta(BaseInstitutionSerializer.Meta):
        fields = ["id", "country", "kind", "label", "size", "payload", "time_frames"]
        validators = [
            UniqueTogetherValidator(
                queryset=Institution.objects.all(),
                fields=["kind", "label"],
                message="An institution with this label already exists for this kind.",
            )
        ]

    def validate_kind(self, value):
        if self.instance is not None and value != self.instance.kind:
            raise serializers.ValidationError(
                "The kind of an institution cannot be changed."
            )
        return value

    def create(self, validated_data):
        validated_data.pop("country")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("country")
        return super().update(instance, validated_data)
