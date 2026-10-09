from rest_framework.fields import IntegerField

from common.models import UserSettings

from ._base import LCCModelSerializer


class UserSettingsSerializer(LCCModelSerializer):
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
                        "government_probability_for",
                        "parliament_majority_probability_for",
                        "parliament_opposition_probability_for",
                        "court_probability_for",
                    }
                }
            case _:
                return fields
