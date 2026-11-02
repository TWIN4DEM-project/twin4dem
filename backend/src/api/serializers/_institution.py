from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from common.models import Institution, TimeFrame, VirtualTimeline

from ._base import LCCModelSerializer


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


class InstitutionSerializer(LCCModelSerializer):
    time_frames = TimeFrameSerializer(many=True, required=False)

    class Meta:
        model = Institution
        fields = ["id", "label", "size", "payload", "time_frames"]

    @transaction.atomic
    def create(self, validated_data):
        frames = validated_data.pop("time_frames", [])
        institution = Institution(**validated_data)
        try:
            institution.full_clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(serializers.as_serializer_error(e))
        if not frames and institution.time_frame_siblings().exists():
            raise serializers.ValidationError(
                {
                    "time_frames": [
                        "Without time frames the institution is active at all times, "
                        "so it would overlap the other institutions of the same kind."
                    ]
                }
            )
        institution.save()
        self._occupy_time_frames(institution, frames)
        return institution

    def _occupy_time_frames(self, institution: Institution, frames: list[dict]):
        """Validate and create the time frames of the institution, one at a time."""

        for index, frame in enumerate(frames):
            try:
                TimeFrame.objects.occupy(institution, **frame)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"time_frames": {index: e.messages}})
