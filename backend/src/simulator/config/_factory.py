from simulator.adapters import AdapterFactory

from ._adapter import GovernmentConfigAdapter, ParliamentConfigAdapter


class ConfigAdapters(AdapterFactory):
    def new_government_adapter(self) -> GovernmentConfigAdapter:
        return GovernmentConfigAdapter()

    def new_parliament_adapter(self) -> ParliamentConfigAdapter:
        return ParliamentConfigAdapter()
