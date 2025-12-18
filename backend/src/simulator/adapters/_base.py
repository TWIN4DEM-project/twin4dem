from abc import ABCMeta, abstractmethod
from typing import Generic

from simulator.common import TInput, TAgent, TOutput
from simulator.executive import Government


class Adapter(Generic[TInput, TOutput], metaclass=ABCMeta):
    @abstractmethod
    def convert(self, input_value: TInput) -> TOutput:
        pass


class GovernmentAdapter(Adapter[TInput, Government], metaclass=ABCMeta):
    pass


class AgentAdapter(Adapter[TInput, TAgent], metaclass=ABCMeta):
    pass
