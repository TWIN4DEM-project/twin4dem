from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from common.models import Country, UserSettings

from ._base import LCCModelSerializer


class AllowedUserSettingsField(serializers.PrimaryKeyRelatedField):
    """Accepts the requesting user's settings, or any settings for a superuser."""

    def get_queryset(self):
        user = self.context["request"].user
        if user.is_superuser:
            return UserSettings.objects.all()
        return UserSettings.objects.filter(user=user)


class CountrySerializer(LCCModelSerializer):
    user_settings = AllowedUserSettingsField()

    class Meta:
        model = Country
        fields = ["id", "name", "user_settings"]
        validators = [
            UniqueTogetherValidator(
                queryset=Country.objects.all(),
                fields=["user_settings", "name"],
                message="A country with this name already exists in these settings.",
            )
        ]

    def validate_user_settings(self, value):
        if self.instance is not None and value != self.instance.user_settings:
            raise serializers.ValidationError(
                "A country cannot be moved to other settings."
            )
        return value
