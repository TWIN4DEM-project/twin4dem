import importlib
import json
from pathlib import Path
from typing import Callable

import pytest


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
