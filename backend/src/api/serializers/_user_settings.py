from rest_framework.fields import IntegerField

from common.models import UserSettings

from ._base import LCCModelSerializer
from ._party_settings import PartySettingsSerializer


class UserSettingsSerializer(LCCModelSerializer):
    parties = PartySettingsSerializer(many=True, read_only=True)
    user_id = IntegerField(read_only=True)

    class Meta:
        model = UserSettings
        exclude = ("user",)

    def get_fields(self):
        fields = super().get_fields()
        view = self.context.get("view")

        if view is None:
            return fields

        match view:
            case "list":
                return {
                    name: field
                    for name, field in fields.items()
                    if name
                    in {
                        "id",
                        "label",
                        "government_size",
                        "government_connectivity_degree",
                        "parliament_size",
                        "court_size",
                    }
                }
            case _:
                return fields
