import importlib
from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "common"

    def ready(self):
        importlib.import_module(".signals", __package__)
