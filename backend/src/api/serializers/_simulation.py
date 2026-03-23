import os
from typing import Literal

from django.db.models import Max
from rest_framework import serializers

from api.serializers._base import LCCModelSerializer
from common.models import (
    Cabinet,
    Simulation,
    SimulationParams,
    Parliament,
    Court,
    SimulationLogEntry,
    PathSubmodelInfo,
    VbarSubmodelInfo,
    SubmodelType,
    AggrandisementUnit,
)
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


class SimulationListSerializer(LCCModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = Simulation
        fields = [
            "id",
            "status",
            "current_step",
            "created_at",
            "updated_at",
            "label",
        ]

    def get_label(self, obj: Simulation):
        if (b := obj.batch.first()) is None:
            return f"random simulation {obj.id}"
        else:
            batch_text = str(b) if b.file_name else f"batch {b}"
            return f"user simulation {obj.id}{os.linesep}{batch_text}"


class SimulationSerializer(SimulationListSerializer):
    max_step_count = serializers.SerializerMethodField()
    params = serializers.SerializerMethodField()

    class Meta:
        model = Simulation
        fields = [
            "id",
            "created_at",
            "updated_at",
            "status",
            "current_step",
            "office_retention_sensitivity",
            "social_influence_susceptibility",
            "params",
            "label",
            "max_step_count",
        ]

    def get_max_step_count(self, obj: Simulation):
        b = obj.batch.first()
        if b is None:
            return None
        return AggrandisementUnit.objects.filter(batch=b).aggregate(
            max_step_no=Max("step_no")
        )["max_step_no"]

    def get_params(self, obj: Simulation):
        qs = obj.params.all()
        return SimulationParamSerializer(qs, many=True).data

    def to_internal_value(self, data):
        return super().to_internal_value(data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        if "maxStepCount" in representation and representation["maxStepCount"] is None:
            representation.pop("maxStepCount")

        return representation


SubmodelTypeLiteral = Literal[
    SubmodelType.EXECUTIVE, SubmodelType.LEGISLATIVE, SubmodelType.JUDICIARY
]


class SimulationWithVoteStateSerializer(SimulationSerializer):
    results = serializers.SerializerMethodField()

    class Meta(SimulationSerializer.Meta):
        model = Simulation
        fields = SimulationSerializer.Meta.fields + ["results"]

    def _get_result(
        self, log_entry: SimulationLogEntry, submodel_type: SubmodelTypeLiteral
    ):
        """
        Helper function to extract the result structure from a submodel.

        :param log_entry: The Simulation Log Entry to extract the results from.
        :type log_entry: SimulationLogEntry
        :param submodel_type: The type of results to extract from the Log Entry.
        :type submodel_type: SubmodelTypeLiteral
        """
        for submodel in log_entry.submodels.all():
            if submodel.submodel_type == submodel_type:
                additional_info: VbarSubmodelInfo | PathSubmodelInfo = (
                    submodel.additional_info
                )
                result = {
                    "approved": submodel.approved,
                    "votes": additional_info.votes,
                }

                if isinstance(additional_info, VbarSubmodelInfo):
                    result["vbar"] = additional_info.vbar
                    result["type"] = (
                        "parliament"
                        if submodel.submodel_type == SubmodelType.LEGISLATIVE
                        else "court"
                    )

                else:
                    result["path"] = additional_info.path
                    result["type"] = "cabinet"

                return result

    def get_results(self, obj: Simulation):
        # retrieve last legislative and judiciary voting results
        last_legislative = (
            obj.log.filter(last_decision_type="legislative")
            .order_by("-step_no")
            .prefetch_related("submodels")
            .first()
        )

        last_judiciary = (
            obj.log.filter(last_decision_type="judiciary")
            .order_by("-step_no")
            .prefetch_related("submodels")
            .first()
        )

        # handle empty result cases
        if last_legislative is None and last_judiciary is None:
            cabinet = None
        # if the last legislative is None, but the judiciary is not None
        elif last_legislative is None:
            cabinet = self._get_result(last_judiciary, SubmodelType.EXECUTIVE)
        # if the last last_judiciary is None, but the legislative is not None
        elif last_judiciary is None:
            cabinet = self._get_result(last_legislative, SubmodelType.EXECUTIVE)
        # if both have a value
        else:
            if last_legislative.id < last_judiciary.id:
                cabinet = self._get_result(last_judiciary, SubmodelType.EXECUTIVE)
            else:
                cabinet = self._get_result(last_legislative, SubmodelType.EXECUTIVE)

        # extract parliament and court results
        parliament = None
        if last_legislative is not None:
            parliament = self._get_result(last_legislative, SubmodelType.LEGISLATIVE)

        court = None
        if last_judiciary is not None:
            court = self._get_result(last_judiciary, SubmodelType.JUDICIARY)

        return [result for result in [cabinet, parliament, court] if result is not None]


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
