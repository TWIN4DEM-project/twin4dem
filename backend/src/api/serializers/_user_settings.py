from rest_framework.fields import IntegerField
from rest_framework.serializers import SerializerMethodField

from common.models import UserSettings

from ._base import LCCModelSerializer


class UserSettingsSerializer(LCCModelSerializer):
    user_id = IntegerField(read_only=True)
    parties = SerializerMethodField()

    class Meta:
        model = UserSettings
        exclude = ("user",)

    def get_parties(self, obj: UserSettings) -> list[dict]:
        """Legacy flat list of the default country's parties, kept for backwards
        compatibility with the payload of the former `PartySettings` model."""
        country = obj.default_country
        if country is None:
            return []
        return [self._party_payload(party) for party in country.parties.order_by("id")]

    @staticmethod
    def _party_payload(party) -> dict:
        position = party.latest_position
        return {
            "id": party.id,
            "label": party.label,
            "position": position.position if position is not None else None,
        }

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
                    }
                }
            case _:
                return fields
