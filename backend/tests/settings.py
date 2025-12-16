from twin4dem.settings import *  # noqa: F401, F403
from twin4dem.celery import app  # noqa: F401


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
