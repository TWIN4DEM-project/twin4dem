from ._base import LCCModelSerializer
from common.models import Party


class PartySettingsSerializer(LCCModelSerializer):
    class Meta:
        model = Party
        fields = ("id", "label", "member_count", "position")
