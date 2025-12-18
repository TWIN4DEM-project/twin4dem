from simulator.adapters import AdapterFactory

from ._adapter import GovernmentConfigAdapter


class ConfigAdapters(AdapterFactory):
    def new_government_adapter(self) -> GovernmentConfigAdapter:
        return GovernmentConfigAdapter()
