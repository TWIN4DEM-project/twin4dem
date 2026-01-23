from pathlib import Path
from twin4dem.settings import *  # noqa: F401, F403
from twin4dem.celery import app  # noqa: F401


TESTS_DIR = Path(__file__).parent


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
FIXTURE_DIRS = [TESTS_DIR / "data" / "fixtures"]
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
ADAPTER_FACTORY = "simulator.db.DbAdapters"
SIMULATION_PERSISTENCE_BACKEND = "simulator.persistence.DjangoSimulationPersistence"
