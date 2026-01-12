from abc import ABCMeta, abstractmethod
from typing import Generic, Any

from simulator.common import TInput, TAgent, TOutput
from simulator.executive import Government
from simulator.legislative import Parliament
from simulator.judiciary import Council


class Adapter(Generic[TInput, TOutput], metaclass=ABCMeta):
    @abstractmethod
    def convert(self, *args: TInput, **kwargs: Any) -> TOutput:
        pass


class GovernmentAdapter(Adapter[TInput, Government], metaclass=ABCMeta):
    pass


class ParliamentAdapter(Adapter[TInput, Parliament], metaclass=ABCMeta):
    pass


class CouncilAdapter(Adapter[TInput, Council], metaclass=ABCMeta):
    pass


class AgentAdapter(Adapter[TInput, TAgent], metaclass=ABCMeta):
    pass
