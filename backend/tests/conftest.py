import importlib
import json
from pathlib import Path
from typing import Callable

import pytest
from django.core.management import call_command
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
