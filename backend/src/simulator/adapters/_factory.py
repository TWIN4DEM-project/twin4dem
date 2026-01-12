from abc import abstractmethod, ABCMeta

from simulator.adapters import GovernmentAdapter, ParliamentAdapter, CouncilAdapter
from simulator.common import TInput


class AdapterFactory(metaclass=ABCMeta):
    @abstractmethod
    def new_government_adapter(self) -> GovernmentAdapter[TInput]:
        pass

    @abstractmethod
    def new_parliament_adapter(self) -> ParliamentAdapter[TInput]:
        pass

    @abstractmethod
    def new_council_adapter(self) -> CouncilAdapter[TInput]:
        pass
