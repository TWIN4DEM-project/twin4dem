from rest_framework import serializers

from common.fields import SeparatedValuesField


class SeparatedValuesSerializerField(serializers.Field):
    def __init__(self, *, model_field: SeparatedValuesField, **kwargs):
        self.model_field = model_field
        super().__init__(**kwargs)

    def to_representation(self, value):
        if value is None:
            return None
        return list(value)

    def to_internal_value(self, data):
        if data is None:
            return None

        if not isinstance(data, (list, tuple, set, frozenset)):
            raise serializers.ValidationError("Expected a list of values")

        try:
            return self.model_field.to_python(data)
        except Exception as exc:
            raise serializers.ValidationError(str(exc)) from exc
