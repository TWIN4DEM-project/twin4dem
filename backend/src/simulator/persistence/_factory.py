from importlib import import_module
from django.conf import settings
from ._base import SimulationPersistence


def get_simulation_persistence() -> SimulationPersistence:
    fqcn = getattr(settings, "SIMULATION_PERSISTENCE_BACKEND")
    last_dot_idx = fqcn.rindex(".")
    module_name = fqcn[:last_dot_idx]
    class_name = fqcn[last_dot_idx + 1 :]
    module = import_module(module_name)
    cls = getattr(module, class_name)
    return cls()
