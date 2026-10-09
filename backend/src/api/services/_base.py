from abc import ABCMeta, abstractmethod
from random import randint, sample

from api.serializers import SimulationSerializer
from common.models import (
    UserSettings,
    SimulationInstitution,
    Institution,
    Simulation,
    Minister,
    MinisterLink,
    Country,
)


class SimulationBuilder(metaclass=ABCMeta):
    _WEIGHTS_COUNT = 6

    def __init__(
        self, settings: UserSettings, weights_count: int = _WEIGHTS_COUNT
    ) -> None:
        self._user_settings = settings
        self._weights_count = weights_count
        self._simulation: Simulation | None = None
        self._cabinet: Institution | None = None
        self._parliament: Institution | None = None
        self._court: Institution | None = None

    @classmethod
    def _get_label(
        cls, simulation, user_settings: UserSettings, suffix: str = ""
    ) -> str:
        return f"{user_settings.user.username}-simulation-{simulation.id:06}{suffix}"

    @abstractmethod
    def _create_cabinet(self) -> Institution:
        pass

    @abstractmethod
    def _create_parliament(self) -> Institution:
        pass

    @abstractmethod
    def _create_court(self) -> Institution:
        pass

    @abstractmethod
    def _init_aggrandisement_batch(self) -> None:
        pass

    @staticmethod
    def _link_institution_to_simulation(
        simulation: Simulation | None, institution: Institution | None
    ) -> SimulationInstitution:
        assert simulation is not None
        assert institution is not None
        ok, result = SimulationInstitution.objects.get_or_create(
            simulation=simulation,
            institution=institution,
        )
        assert ok
        return result

    def create(self, serializer: SimulationSerializer) -> Simulation:
        self._simulation = serializer.save(user_settings=self._user_settings)
        assert self._simulation is not None

        self._cabinet = self._create_cabinet()
        self._parliament = self._create_parliament()
        self._court = self._create_court()
        self._init_aggrandisement_batch()

        return self._simulation

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

    def _get_country(self) -> Country:
        country = self._user_settings.countries.first()
        assert country is not None
        return country
