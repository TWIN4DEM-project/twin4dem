import os

from celery import Celery
from kombu.serialization import register
from simulator.model.serialization.pydantic_serializer import (
    pydantic_dumps,
    pydantic_loads,
)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twin4dem.settings")

app = Celery("proj")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

register(
    "pydantic",
    pydantic_dumps,
    pydantic_loads,
    content_type="application/x-pydantic",
    content_encoding="utf-8",
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
