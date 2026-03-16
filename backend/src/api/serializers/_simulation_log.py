from rest_framework import serializers

from api.serializers._base import LCCModelSerializer
from common.models import SimulationLogEntry, SimulationSubmodelLogEntry


class SimulationSubmodelLogSerializer(LCCModelSerializer):
    votes_for = serializers.SerializerMethodField()
    abstentions = serializers.SerializerMethodField()
    votes_against = serializers.SerializerMethodField()

    class Meta:
        model = SimulationSubmodelLogEntry
        fields = [
            "submodel_type",
            "approved",
            "votes_for",
            "votes_against",
            "abstentions",
        ]

    def get_votes_for(self, obj: SimulationSubmodelLogEntry):
        return sum(1 for label in obj.additional_info.votes.values() if label == 1)

    def get_votes_against(self, obj: SimulationSubmodelLogEntry):
        return sum(1 for label in obj.additional_info.votes.values() if label == 0)

    def get_abstentions(self, obj: SimulationSubmodelLogEntry):
        return sum(1 for label in obj.additional_info.votes.values() if label is None)


class SimulationLogSerializer(LCCModelSerializer):
    submodel_results = serializers.SerializerMethodField()

    class Meta:
        model = SimulationLogEntry
        fields = [
            "simulation_id",
            "step_no",
            "approved",
            "last_decision_type",
            "aggrandisement_path",
            "submodel_results",
        ]

    def get_submodel_results(self, obj: SimulationLogEntry):
        return SimulationSubmodelLogSerializer(obj.submodels, many=True).data
