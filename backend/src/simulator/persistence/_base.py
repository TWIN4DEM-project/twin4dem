from abc import ABCMeta, abstractmethod

from common.dto import SimulationStepResult


class SimulationPersistence(metaclass=ABCMeta):
    @abstractmethod
    def persist_step(self, payload: SimulationStepResult | dict) -> None:
        pass

    @abstractmethod
    def can_perform_step(self, simulation_id: int, step_no: int) -> bool:
        pass
