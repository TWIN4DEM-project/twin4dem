from rest_framework import serializers

from api.serializers._base import LCCModelSerializer
from common.models import Cabinet, Simulation, SimulationParams, Parliament, Court
from ._executive import CabinetSerializer
from ._judiciary import CourtSerializer
from ._legislative import ParliamentSerializer


class SimulationParamSerializer(serializers.Serializer):
    type = serializers.JSONField()
    data = serializers.DictField()

    def to_representation(self, instance: SimulationParams):
        obj = instance.params
        if obj is None:
            return None

        if isinstance(obj, Cabinet):
            return {
                "type": "cabinet",
                "cabinet": CabinetSerializer(obj).data,
            }
        elif isinstance(obj, Parliament):
            return {
                "type": "parliament",
                "parliament": ParliamentSerializer(obj).data,
            }
        elif isinstance(obj, Court):
            return {"type": "court", "court": CourtSerializer(obj).data}
        else:
            raise NotImplementedError(
                f"Unsupported simulation param type: {obj.__class__.__name__}"
            )


class SimulationSerializer(LCCModelSerializer):
    params = serializers.SerializerMethodField()

    class Meta:
        model = Simulation
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "current_step",
            "office_retention_sensitivity",
            "social_influence_susceptibility",
        ]
        fields = [
            "id",
            "created_at",
            "updated_at",
            "status",
            "current_step",
            "office_retention_sensitivity",
            "social_influence_susceptibility",
            "params",
        ]

    def get_params(self, obj: Simulation):
        qs = obj.params.all()
        return SimulationParamSerializer(qs, many=True).data

    def to_internal_value(self, data):
        return super().to_internal_value(data)


class SimulationListSerializer(LCCModelSerializer):
    class Meta:
        model = Simulation
        fields = [
            "id",
            "status",
            "current_step",
            "created_at",
            "updated_at",
        ]


class SimulationPatchSerializer(LCCModelSerializer):
    class Meta:
        model = Simulation
        fields = ["status"]

    def validate(self, attrs):
        unexpected = set(self.initial_data.keys()) - {"status"}
        if unexpected:
            raise serializers.ValidationError(
                {key: "not allowed to update field" for key in unexpected}
            )
        return attrs
