import importlib
import json
from pathlib import Path
from typing import Callable

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from common.models import Simulation
from common.models import UserSettings


@pytest.fixture(autouse=True)
def celery_eager(settings):
    """
    Make Celery tasks execute synchronously in tests.
    That way .delay().get() just runs the function directly.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture(scope="session", autouse=True)
def load_celery():
    importlib.import_module("twin4dem.celery")


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


@pytest.fixture(scope="session")
def load_json(data_dir) -> Callable[[str], dict]:
    def _(filename: str) -> dict:
        with open(data_dir / filename, "r") as fp:
            return json.load(fp)

    return _


@pytest.fixture
def load_pydantic(load_json) -> Callable[[str], dict]:
    def _(filename: str) -> dict:
        return {
            "__pydantic_model__": "GovernmentConfig",
            "data": load_json(filename),
        }

    return _


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker, data_dir):
    with django_db_blocker.unblock():
        call_command("loaddata", "user_data.json")
        call_command("loaddata", "user_settings.json")


@pytest.fixture
def admin_user(django_db_setup, django_user_model):
    return django_user_model.objects.get(username="test_admin")


@pytest.fixture
def test_settings(admin_user):
    return UserSettings.objects.get(user=admin_user)


@pytest.fixture
def simulation_id(request) -> int:
    return getattr(request, "param", 1)


@pytest.fixture
def load_simulation(db, django_db_blocker):
    """
    Load a fixture file and return Simulation(pk=simulation_id).
    Keeps the DB-first approach consistent across branches.
    """

    def _load(fixture_file: str, simulation_id: int = 1) -> Simulation:
        with django_db_blocker.unblock():
            call_command("loaddata", fixture_file)
            return Simulation.objects.get(pk=simulation_id)

    return _load


@pytest.fixture
def executive_simulation(load_simulation, simulation_id):
    return load_simulation(
        f"executive/scenario{simulation_id}.json", simulation_id=simulation_id
    )


@pytest.fixture
def judiciary_simulation(load_simulation, simulation_id):
    return load_simulation("judiciary/judiciary.json", simulation_id=simulation_id)


@pytest.fixture
def legislative_simulation(load_simulation, simulation_id):
    return load_simulation("legislative/legislative.json", simulation_id=simulation_id)


@pytest.fixture
def institution_params():
    """
    Generic helper to fetch the first SimulationParam.params for a given institution model.
    Usage: institution_params(simulation, Cabinet) -> Cabinet params instance
    """

    def _get(simulation, model_cls):
        ct = ContentType.objects.get_for_model(model_cls)
        qs = simulation.params.filter(type=ct).select_related("type")
        obj = qs.first()
        assert obj is not None, (
            f"No params found for model {model_cls.__name__} in Simulation(id={simulation.id}). "
            f"Did you load the right fixture?"
        )
        return obj.params

    return _get
