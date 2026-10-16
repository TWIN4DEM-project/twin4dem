import pytest
from django.utils import timezone

from common.models import (
    AggrandisementBatch,
    AggrandisementUnit,
    Simulation,
)

# world.json: country 1; pk 42 is free for ad-hoc simulations
TEST_SIMULATION_ID = 42
COUNTRY_ID = 1


@pytest.fixture
def world_simulation(test_settings) -> Simulation:
    return Simulation.objects.create(
        pk=TEST_SIMULATION_ID,
        user_settings=test_settings,
        country_id=COUNTRY_ID,
        timeline=test_settings.timelines.get(),
    )


@pytest.fixture
def make_aggrandisement_unit():
    def _make(simulation, step_no):
        batch = AggrandisementBatch.objects.create(
            simulation=simulation,
            start_date=timezone.now(),
            end_date=timezone.now(),
        )
        return AggrandisementUnit.objects.create(batch=batch, step_no=step_no)

    return _make


@pytest.fixture
def configured_global_beliefs(targeted_and_fallback):
    """Set the targeted agent's beliefs to 0.0 and the fallback agent's to 1.0."""
    targeted, fallback = targeted_and_fallback
    targeted.personal_opinion = 0.0
    targeted.appointing_group_opinion = 0.0
    targeted.supporting_group_opinion = 0.0
    targeted.save(
        update_fields=[
            "personal_opinion",
            "appointing_group_opinion",
            "supporting_group_opinion",
        ]
    )
    fallback.personal_opinion = 1.0
    fallback.appointing_group_opinion = 1.0
    fallback.supporting_group_opinion = 1.0
    fallback.save(
        update_fields=[
            "personal_opinion",
            "appointing_group_opinion",
            "supporting_group_opinion",
        ]
    )
    return targeted, fallback
