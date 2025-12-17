from caseswitcher import to_snake, to_camel
from rest_framework.serializers import ModelSerializer


class LCCModelSerializer(ModelSerializer):
    @staticmethod
    def _apply_transform(obj, transform):
        result = obj
        children = []
        if isinstance(obj, dict):
            result = {transform(k): v for k, v in obj.items()}
            children.extend(obj.values())
        elif isinstance(obj, (list, set, frozenset, tuple)):
            children.extend(obj)
        else:
            pass

        for c in children:
            LCCModelSerializer._apply_transform(c, transform)

        return result

    def to_internal_value(self, data):
        return super().to_internal_value(self._apply_transform(data, to_snake))

    def to_representation(self, instance):
        return self._apply_transform(super().to_representation(instance), to_camel)
