from simulator.adapters import AdapterFactory

from simulator.db._adapter import GovernmentDbAdapter, ParliamentDbAdapter


class DbAdapters(AdapterFactory):
    def new_parliament_adapter(self) -> ParliamentDbAdapter:
        return ParliamentDbAdapter()

    def new_government_adapter(self) -> GovernmentDbAdapter:
        return GovernmentDbAdapter()
