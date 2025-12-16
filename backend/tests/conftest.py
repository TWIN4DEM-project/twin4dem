import importlib
import pytest


@pytest.fixture(scope="session", autouse=True)
def load_celery():
    importlib.import_module("twin4dem.celery")
