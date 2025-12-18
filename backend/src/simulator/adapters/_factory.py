from abc import abstractmethod, ABCMeta

from simulator.adapters import GovernmentAdapter
from simulator.common import TInput


class AdapterFactory(metaclass=ABCMeta):
    @abstractmethod
    def new_government_adapter(self) -> GovernmentAdapter[TInput]:
        pass
