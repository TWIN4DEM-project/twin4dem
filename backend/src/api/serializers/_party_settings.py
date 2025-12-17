from ._base import LCCModelSerializer
from common.models import PartySettings


class PartySettingsSerializer(LCCModelSerializer):
    class Meta:
        model = PartySettings
        fields = ("id", "label", "member_count", "position")
