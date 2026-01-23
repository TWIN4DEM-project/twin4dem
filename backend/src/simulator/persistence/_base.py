from abc import ABCMeta, abstractmethod

from common.dto import SimulationStepResult


class SimulationPersistence(metaclass=ABCMeta):
    @abstractmethod
    def persist_step(self, payload: SimulationStepResult | dict) -> None:
        pass
