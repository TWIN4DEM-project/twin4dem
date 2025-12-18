from simulator.adapters import AdapterFactory

from simulator.db._adapter import GovernmentDbAdapter


class DbAdapters(AdapterFactory):
    def new_government_adapter(self) -> GovernmentDbAdapter:
        return GovernmentDbAdapter()
