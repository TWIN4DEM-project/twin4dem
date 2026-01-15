from simulator.adapters import AdapterFactory, CouncilAdapter
from simulator.common import TInput

from simulator.db._adapter import (
    GovernmentDbAdapter,
    ParliamentDbAdapter,
    CouncilDbAdapter,
)


class DbAdapters(AdapterFactory):
    def new_council_adapter(self) -> CouncilAdapter[TInput]:
        return CouncilDbAdapter()

    def new_parliament_adapter(self) -> ParliamentDbAdapter:
        return ParliamentDbAdapter()

    def new_government_adapter(self) -> GovernmentDbAdapter:
        return GovernmentDbAdapter()
