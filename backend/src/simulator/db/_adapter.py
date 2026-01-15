import random
from typing import Any

from django.contrib.contenttypes.models import ContentType

from common.models import (
    Simulation,
    Cabinet,
    Minister as MinisterModel,
    Parliament as ParliamentModel,
    MemberOfParliament,
    PartySettings,
)
from simulator.adapters import (
    GovernmentAdapter,
    AgentAdapter,
    ParliamentAdapter,
    CouncilAdapter,
)
from simulator.executive import Government, Minister
from simulator.judiciary import Council
from simulator.legislative import Parliament, MP


def _random_gauss(
    center: float, spread: float = 1.0, lo: float = 0.0, hi: float = 1.0
) -> float:
    while not (lo <= (x := random.gauss(center, spread)) <= hi):
        continue
    return x


def _random_frequency(center: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return hi if random.random() < center else lo


class MinisterDbAdapter(AgentAdapter[MinisterModel, Minister]):
    def convert(self, value: MinisterModel) -> Minister:
        random_opinion = _random_gauss(value.cabinet.government_probability_for, 0.1)
        personal_opinion = int(round(random_opinion))
        return Minister(
            id=value.id,
            T_i="Minister",
            is_pm=value.is_prime_minister,
            P_i=value.party.position,
            S_i=value.influence,
            W=value.weights,
            o_i=personal_opinion,
            # support group 1 = ones who have the power to affect the status of the minister (appoint, revoke, etc)
            o_sup1=_random_frequency(value.cabinet.government_probability_for),
            # support group 2 = people who are directly benefitting from ministers getting more power
            # setting this to 1.0 until better ideas about how to compute this value emerge
            o_sup2=1.0,
        )


class GovernmentDbAdapter(GovernmentAdapter[int]):
    def __init__(self):
        self.__minister_adapter = MinisterDbAdapter()

    @staticmethod
    def _build_network(ministers: list[MinisterModel]) -> dict[int, list[int]]:
        return {
            minister.id: [n.id for n in minister.neighbours_in.all()]
            for minister in ministers
        }

    def convert(self, simulation_id: int, **kwargs: Any) -> Government:
        value = Simulation.objects.get(pk=simulation_id)
        param = (
            value.params.filter(type=ContentType.objects.get_for_model(Cabinet))
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
            alpha=value.social_influence_susceptibility,
            gamma=value.office_retention_sensitivity,
            epsilon=value.user_settings.abstention_threshold,
            ministers=ministers,
            network=self._build_network(minister_models),
        )


class MPDbAdapter(AgentAdapter[MemberOfParliament, MP]):
    def __init__(self, majority_prob_for: float, opposition_prob_for: float):
        self._majority_for = majority_prob_for
        self._opposition_for = opposition_prob_for

    def convert(self, mp: MemberOfParliament) -> MP:
        party_position = mp.party.position
        if party_position == PartySettings.PartyPosition.MAJORITY:
            prob_distribution_center = self._majority_for
            o_sup1 = 1
        elif party_position == PartySettings.PartyPosition.OPPOSITION:
            prob_distribution_center = self._opposition_for
            o_sup1 = 0
        else:
            prob_distribution_center = 0.5
            o_sup1 = 0

        personal_opinion = int(
            round(_random_gauss(prob_distribution_center, spread=0.1))
        )
        return MP(
            id=mp.id,
            T_i="mp",
            P_i=mp.party.label,
            W=mp.weights,
            is_head=mp.is_head,
            S_i=0,
            o_i=personal_opinion,
            o_sup1=o_sup1,
            o_sup2=0,
        )


class ParliamentDbAdapter(ParliamentAdapter[int]):
    def convert(self, simulation_id: int) -> Parliament:
        value = Simulation.objects.get(pk=simulation_id)
        sim_parliaments = value.params.filter(
            type=ContentType.objects.get_for_model(ParliamentModel)
        ).select_related("type")
        if not sim_parliaments.exists():
            raise ValueError(f"simulation {value.id} does not have a parliament")
        parliament: ParliamentModel = sim_parliaments.first().params
        parliament_members = list(
            parliament.members.all().prefetch_related("parliament")
        )
        mp_adapter = MPDbAdapter(
            parliament.majority_probability_for, parliament.opposition_probability_for
        )
        mps = list(map(mp_adapter.convert, parliament_members))
        return Parliament(
            mps=mps,
            n_party=len(value.user_settings.parties.all()),
            n_sits=[p.member_count for p in value.user_settings.parties.all()],
            alpha=value.social_influence_susceptibility,
            epsilon=value.user_settings.abstention_threshold,
            gamma=value.office_retention_sensitivity,
        )


class CouncilDbAdapter(CouncilAdapter[int]):
    def convert(self, simulation_id: int) -> Council:
        value = Simulation.objects.get(pk=simulation_id)
        return Council(
            judges=[],
            alpha=value.social_influence_susceptibility,
            epsilon=value.user_settings.abstention_threshold,
            gamma=value.office_retention_sensitivity,
            network={},
        )
