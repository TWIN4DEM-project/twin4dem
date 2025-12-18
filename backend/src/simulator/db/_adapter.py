import random

from django.contrib.contenttypes.models import ContentType

from common.models import Simulation, Cabinet, Minister as MinisterModel
from simulator.adapters import GovernmentAdapter, AgentAdapter
from simulator.executive import Government, Minister


class MinisterDbAdapter(AgentAdapter[MinisterModel, Minister]):
    @staticmethod
    def _random_weights(n: int = 6) -> list[float]:
        x = [random.expovariate(1.0) for _ in range(n)]
        s = sum(x)
        return [x_i / s for x_i in x]

    @staticmethod
    def _random_gauss(
        center: float, spread: float = 1.0, lo: float = 0.0, hi: float = 1.0
    ) -> float:
        while not (lo <= (x := random.gauss(center, spread)) <= hi):
            continue
        return x

    def convert(self, input_value: MinisterModel) -> Minister:
        return Minister(
            id=input_value.id,
            T_i="Minister",
            is_pm=input_value.is_prime_minister,
            P_i=input_value.party.position,
            S_i=input_value.influence,
            W=self._random_weights(6),
            o_i=self._random_gauss(input_value.cabinet.government_probability_for),
            o_sup1=0.5,
            o_sup2=0.5,
        )


class GovernmentDbAdapter(GovernmentAdapter[Simulation]):
    def __init__(self):
        self.__minister_adapter = MinisterDbAdapter()

    @staticmethod
    def _build_network(ministers: list[MinisterModel]) -> dict[int, list[int]]:
        return {
            minister.id: [n.id for n in minister.neighbours_in.all()]
            for minister in ministers
        }

    def convert(self, input_value: Simulation) -> Government:
        param = (
            input_value.params.filter(type=ContentType.objects.get_for_model(Cabinet))
            .select_related("type")
            .first()
        )
        cabinet: Cabinet = param.params if param else None
        minister_models = list(
            cabinet.ministers.all().prefetch_related("cabinet", "neighbours_in")
        )
        ministers = list(map(self.__minister_adapter.convert, minister_models))

        return Government(
            pact=cabinet.legislative_probability,
            alpha=0.5,
            gamma=5.5,
            epsilon=input_value.user_settings.abstention_threshold,
            ministers=ministers,
            network=self._build_network(minister_models),
        )
