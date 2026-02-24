import pytest
from django.contrib.contenttypes.models import ContentType

from common.dto import SimulationStepResult
from common.models import (
    Cabinet,
    Parliament,
    SimulationLogEntry,
    SimulationParams,
)
from simulator.persistence import get_simulation_persistence
from simulator.tasks import executive_submodel, subsequent_submodel


@pytest.mark.django_db
def test_step_by_step_simulation_persists_flow(load_simulation):
    simulation = load_simulation("complete/legislative_simulation.json", simulation_id=1)
    cabinet = Cabinet.objects.get(pk=1)
    parliament = Parliament.objects.get(pk=1)

    SimulationParams.objects.filter(simulation=simulation).delete()
    SimulationParams.objects.create(
        simulation=simulation,
        type=ContentType.objects.get_for_model(Cabinet),
        content_id=cabinet.id,
    )
    SimulationParams.objects.create(
        simulation=simulation,
        type=ContentType.objects.get_for_model(Parliament),
        content_id=parliament.id,
    )

    cabinet.government_probability_for = 1.0
    cabinet.legislative_probability = 1.0
    cabinet.save(update_fields=["government_probability_for", "legislative_probability"])
    cabinet.ministers.all().update(
        personal_opinion=1, appointing_group_opinion=1, supporting_group_opinion=1
    )
    simulation.office_retention_sensitivity = 25.0
    simulation.save(update_fields=["office_retention_sensitivity"])
    simulation.user_settings.abstention_threshold = 0.0
    simulation.user_settings.save(update_fields=["abstention_threshold"])

    persistence = get_simulation_persistence()
    step_count = 3
    for step_no in range(1, step_count + 1):
        step_input = SimulationStepResult(
            step_no=step_no, simulation_id=simulation.id, results=[]
        ).model_dump(mode="json", by_alias=True)

        step_result = executive_submodel.delay(step_input).get()
        assert step_result["results"][-1]["approved"] is True
        step_result = subsequent_submodel.delay(step_result).get()

        persistence.persist_step(step_result)

        simulation.refresh_from_db()
        assert simulation.current_step == step_no
        assert (
            SimulationLogEntry.objects.filter(simulation=simulation).count() == step_no
        )
        log_entry = SimulationLogEntry.objects.get(simulation=simulation, step_no=step_no)
        assert log_entry.submodels.count() == len(step_result["results"])
