from abc import ABCMeta, abstractmethod
from random import randint, sample

from django.contrib.contenttypes.models import ContentType

from api.serializers import SimulationSerializer
from common.models import (
    UserSettings,
    Cabinet,
    SimulationParams,
    Parliament,
    Court,
    Simulation,
    Minister,
    MinisterLink,
)


class SimulationBuilder(metaclass=ABCMeta):
    _WEIGHTS_COUNT = 6

    def __init__(
        self, settings: UserSettings, weights_count: int = _WEIGHTS_COUNT
    ) -> None:
        self._user_settings = settings
        self._weights_count = weights_count

    @classmethod
    def _get_label(
        cls, simulation, user_settings: UserSettings, suffix: str = ""
    ) -> str:
        return f"{user_settings.user.username}-simulation-{simulation.id:06}{suffix}"

    @abstractmethod
    def _create_cabinet(self, simulation: Simulation) -> Cabinet:
        pass

    @abstractmethod
    def _create_parliament(self, simulation: Simulation) -> Parliament:
        pass

    @abstractmethod
    def _create_court(self, simulation: Simulation) -> Court:
        pass

    def create(self, serializer: SimulationSerializer) -> Simulation:
        sim = serializer.save(user_settings=self._user_settings)
        cab = self._create_cabinet(sim)
        ct = ContentType.objects.get_for_model(Cabinet)
        SimulationParams.objects.create(simulation=sim, type=ct, content_id=cab.id)

        parliament = self._create_parliament(sim)
        ct = ContentType.objects.get_for_model(Parliament)
        SimulationParams.objects.create(
            simulation=sim, type=ct, content_id=parliament.id
        )

        court = self._create_court(sim)
        ct = ContentType.objects.get_for_model(Court)
        SimulationParams.objects.create(simulation=sim, type=ct, content_id=court.id)
        return sim

    @classmethod
    def _build_minister_network(
        cls,
        connectivity_degree: int,
        prime_minister: Minister,
        ministers: list[Minister],
    ) -> list[MinisterLink]:
        all_nodes = ministers + [prime_minister]
        remaining_indegree = {m.id: connectivity_degree for m in ministers}
        links = []

        for m in ministers:
            links.append(MinisterLink(from_minister=prime_minister, to_minister=m))
            remaining_indegree[m.id] -= 1

        for minister in ministers:
            max_out = randint(1, connectivity_degree)

            candidates = [
                m
                for m in all_nodes
                if (
                    m != minister
                    and (m == prime_minister or remaining_indegree.get(m.id, 0) > 0)
                )
            ]

            if not candidates:
                continue

            degree = min(max_out, len(candidates))
            targets = sample(candidates, degree)

            for target in targets:
                links.append(MinisterLink(from_minister=minister, to_minister=target))
                if target != prime_minister:
                    remaining_indegree[target.id] -= 1

        return links
