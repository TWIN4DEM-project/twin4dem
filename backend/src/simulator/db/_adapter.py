import random

from django.contrib.contenttypes.models import ContentType

from common.models import Simulation, Cabinet, Minister as MinisterModel
from simulator.adapters import GovernmentAdapter, AgentAdapter, ParliamentAdapter
from simulator.executive import Government, Minister
from simulator.legislative import Parliament


class MinisterDbAdapter(AgentAdapter[MinisterModel, Minister]):
    @staticmethod
    def _random_gauss(
        center: float, spread: float = 1.0, lo: float = 0.0, hi: float = 1.0
    ) -> float:
        while not (lo <= (x := random.gauss(center, spread)) <= hi):
            continue
        return x

    @staticmethod
    def _random_frequency(center: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return hi if random.random() < center else lo

    def convert(self, input_value: MinisterModel) -> Minister:
        return Minister(
            id=input_value.id,
            T_i="Minister",
            is_pm=input_value.is_prime_minister,
            P_i=input_value.party.position,
            S_i=input_value.influence,
            W=input_value.weights,
            o_i=self._random_gauss(input_value.cabinet.government_probability_for),
            # support group 1 = ones who have the power to affect the status of the minister (appoint, revoke, etc)
            o_sup1=self._random_frequency(
                input_value.cabinet.government_probability_for
            ),
            # support group 2 = people who are directly benefitting from ministers getting more power
            # setting this to 1.0 until better ideas about how to compute this value emerge
            o_sup2=1.0,
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
            alpha=input_value.social_influence_susceptibility,
            gamma=input_value.office_retention_sensitivity,
            epsilon=input_value.user_settings.abstention_threshold,
            ministers=ministers,
            network=self._build_network(minister_models),
        )


class ParliamentDbAdapter(ParliamentAdapter[Simulation]):
    def convert(self, input_value: Simulation) -> Parliament:
        return Parliament(
            mps=input_value.user_settings.parliament_size,
            n_party=len(input_value.user_settings.parties.all()),
            n_sits=[p.member_count for p in input_value.user_settings.parties.all()],
            alpha=input_value.social_influence_susceptibility,
            epsilon=input_value.user_settings.abstention_threshold,
            gamma=input_value.office_retention_sensitivity,
        )
