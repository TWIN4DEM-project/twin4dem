import pytest
from django.contrib.contenttypes.models import ContentType

from common.models import Simulation, SimulationParams, Cabinet

TEST_APP_NAME = "tests"


@pytest.mark.django_db
def test_create_simulation(test_settings):
    sim = Simulation.objects.create(user_settings=test_settings)

    assert sim.status == Simulation.Status.NEW
    assert sim.current_step == 0
    assert sim.created_at is not None
    assert sim.updated_at is not None
    assert sim in test_settings.simulations.all()


@pytest.mark.django_db
def test_create_simulation_params(test_settings):
    content_type = ContentType.objects.get_for_model(Cabinet)
    sim = Simulation.objects.create(user_settings=test_settings)
    cabinet = Cabinet.objects.create(label="1234", legislative_probability=0.5)
    sp = SimulationParams.objects.create(
        simulation=sim, type=content_type, content_id=cabinet.id
    )

    assert len(sim.params.all()) == 1
    assert sp.params.label == "1234"
    assert cabinet.simulation_param.first() == sp
