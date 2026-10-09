from __future__ import annotations

from django.db import transaction
from django.db.models import Max

from common.dto import SimulationStepResult, SubmodelType as SubmodelTypeDto
from common.models import (
    Simulation,
    SimulationLogEntry,
    SimulationSubmodelLogEntry,
    SubmodelType,
    PathSubmodelInfo,
    VbarSubmodelInfo,
    AggrandisementUnit,
)

from ._base import SimulationPersistence

_SUBMODEL_TYPE_MAP = {
    SubmodelTypeDto.Cabinet: SubmodelType.EXECUTIVE,
    SubmodelTypeDto.Parliament: SubmodelType.LEGISLATIVE,
    SubmodelTypeDto.Court: SubmodelType.JUDICIARY,
}


class DjangoSimulationPersistence(SimulationPersistence):
    def can_perform_step(self, simulation_id: int, step_count: int) -> bool:
        try:
            simulation = Simulation.objects.get(pk=simulation_id)
            simulation_units = AggrandisementUnit.objects.select_related(
                "batch"
            ).filter(batch__simulation_id=simulation.id)
            if not simulation_units.exists():
                return True
            max_step = simulation_units.aggregate(max_step=Max("step_no"))["max_step"]
            return simulation.current_step + step_count <= max_step
        except Simulation.DoesNotExist:
            return False

    def persist_step(self, payload: SimulationStepResult | dict) -> None:
        step_result = self._coerce_input_arg(payload)
        if not step_result.results:
            raise ValueError("simulation step has no submodel results to persist")

        with transaction.atomic():
            simulation = Simulation.objects.select_for_update().get(
                pk=step_result.simulation_id
            )
            simulation.current_step = step_result.step_no
            simulation.save(update_fields=["current_step"])

            final_result = step_result.results[-1]
            last_decision_type = _SUBMODEL_TYPE_MAP[final_result.type]
            aggrandisement_path = self._get_aggrandisement_path(step_result)

            log_entry = SimulationLogEntry.objects.create(
                simulation=simulation,
                step_no=step_result.step_no,
                approved=final_result.approved,
                last_decision_type=last_decision_type,
                aggrandisement_path=aggrandisement_path,
            )

            for result in step_result.results:
                info = self._build_submodel_info(result)
                SimulationSubmodelLogEntry.objects.create(
                    log_entry=log_entry,
                    submodel_type=_SUBMODEL_TYPE_MAP[result.type],
                    approved=result.approved,
                    additional_info=info,
                )

    @staticmethod
    def _get_aggrandisement_path(step_result: SimulationStepResult) -> str | None:
        try:
            return next(
                r.path for r in step_result.results if r.type == SubmodelTypeDto.Cabinet
            )
        except StopIteration:
            raise ValueError(
                "simulation step has no cabinet result for aggrandisement path"
            )

    @staticmethod
    def _build_submodel_info(result):
        match result.type:
            case SubmodelTypeDto.Cabinet:
                return PathSubmodelInfo(votes=result.votes, path=result.path)
            case SubmodelTypeDto.Parliament | SubmodelTypeDto.Court:
                return VbarSubmodelInfo(votes=result.votes, vbar=result.vbar)
            case _:
                raise ValueError(
                    "simulation step result has no path or vbar to persist"
                )

    @staticmethod
    def _coerce_input_arg(payload) -> SimulationStepResult:
        if isinstance(payload, SimulationStepResult):
            return payload
        if isinstance(payload, dict):
            return SimulationStepResult.model_validate(
                payload, by_alias=True, by_name=True
            )
        raise ValueError(f"Unsupported step payload type: {type(payload)}")
