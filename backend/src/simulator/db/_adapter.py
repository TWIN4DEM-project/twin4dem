import random
from typing import Any, Generic, TypeVar

from django.contrib.contenttypes.models import ContentType

from common.models import (
    Simulation,
    Cabinet,
    Minister as MinisterModel,
    Parliament as ParliamentModel,
    MemberOfParliament,
    PartySettings,
    Court as CourtModel,
    Judge as JudgeModel,
    SimulationSubmodelLogEntry,
    SubmodelType,
)
from simulator.adapters import (
    GovernmentAdapter,
    AgentAdapter,
    ParliamentAdapter,
    CouncilAdapter,
)
from simulator.executive import Government, Minister
from simulator.judiciary import Council, Judge
from simulator.legislative import Parliament, MP
from simulator.common import AgentBelief, Weights


def _random_gauss(
    center: float, spread: float = 1.0, lo: float = 0.0, hi: float = 1.0
) -> float:
    while not (lo <= (x := random.gauss(center, spread)) <= hi):
        continue
    return x


def _random_frequency(center: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return hi if random.random() < center else lo


T = TypeVar("T", Cabinet, ParliamentModel, CourtModel)


class RelatedInstitutionFinder(Generic[T]):
    @classmethod
    def _find_institution(cls, simulation: Simulation, model_class: type[T]) -> T:
        related_of_type = simulation.params.filter(
            type=ContentType.objects.get_for_model(model_class)
        ).select_related("type")
        if not related_of_type.exists():
            raise ValueError(
                f"there are no {model_class.__name__} models in simulation {simulation.id}"
            )
        return related_of_type.first().params


class PrevVotesFinder:
    @classmethod
    def _get_prev_votes(
        cls, simulation: Simulation, submodel_type: SubmodelType
    ) -> dict[str, int]:
        previous_submodel_log_entries = SimulationSubmodelLogEntry.objects.filter(
            submodel_type=submodel_type, log_entry__simulation=simulation
        ).order_by("-log_entry__step_no")
        latest_results = previous_submodel_log_entries.first()
        if latest_results is not None:
            return latest_results.additional_info.votes
        return {}


class MinisterDbAdapter(AgentAdapter[MinisterModel, Minister]):
    def convert(self, value: MinisterModel) -> Minister:
        return Minister(
            id=value.id,
            T_i="Minister",
            is_pm=value.is_prime_minister,
            P_i=value.party.position,
            S_i=value.influence,
            W=Weights(value.weights),
            belief=AgentBelief(
                o_i=value.personal_opinion,
                # support group 1 = ones who have the power to affect the status of the minister (appoint, revoke, etc)
                o_sup1=value.appointing_group_opinion,
                # support group 2 = people who are directly benefitting from ministers getting more power
                # setting this to 1.0 until better ideas about how to compute this value emerge
                o_sup2=value.supporting_group_opinion,
            ),
        )


class GovernmentDbAdapter(
    GovernmentAdapter[int], RelatedInstitutionFinder[Cabinet], PrevVotesFinder
):
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
        cabinet = self._find_institution(value, Cabinet)
        minister_models = list(
            cabinet.ministers.all().prefetch_related("cabinet", "neighbours_in")
        )
        ministers = list(map(self.__minister_adapter.convert, minister_models))
        previous_votes = self._get_prev_votes(value, SubmodelType.EXECUTIVE)

        return Government(
            pact=cabinet.legislative_probability,
            alpha=value.social_influence_susceptibility,
            gamma=value.office_retention_sensitivity,
            epsilon=value.user_settings.abstention_threshold,
            ministers=ministers,
            network=self._build_network(minister_models),
            previous_votes=previous_votes,
        )


class MPDbAdapter(AgentAdapter[MemberOfParliament, MP]):
    def __init__(self, majority_prob_for: float, opposition_prob_for: float):
        self._majority_for = majority_prob_for
        self._opposition_for = opposition_prob_for

    def convert(self, mp: MemberOfParliament) -> MP:
        return MP(
            id=mp.id,
            T_i="mp",
            P_i=mp.party.label,
            W=Weights(mp.weights),
            is_head=mp.is_head,
            S_i=0,
            belief=AgentBelief(
                o_i=mp.personal_opinion,
                o_sup1=mp.appointing_group_opinion,
                o_sup2=mp.supporting_group_opinion,
            ),
        )


class ParliamentDbAdapter(
    ParliamentAdapter[int], RelatedInstitutionFinder[ParliamentModel], PrevVotesFinder
):
    def convert(self, simulation_id: int) -> Parliament:
        value = Simulation.objects.get(pk=simulation_id)
        parliament = self._find_institution(value, ParliamentModel)
        parliament_members = list(
            parliament.members.all().prefetch_related("parliament")
        )
        mp_adapter = MPDbAdapter(
            parliament.majority_probability_for, parliament.opposition_probability_for
        )
        mps = list(map(mp_adapter.convert, parliament_members))
        previous_votes = self._get_prev_votes(value, SubmodelType.LEGISLATIVE)
        return Parliament(
            mps=mps,
            n_party=len(value.user_settings.parties.all()),
            n_sits=[p.member_count for p in value.user_settings.parties.all()],
            alpha=value.social_influence_susceptibility,
            epsilon=value.user_settings.abstention_threshold,
            gamma=value.office_retention_sensitivity,
            prev_votes=previous_votes,
        )


class JudgeDbAdapter(AgentAdapter[JudgeModel, Judge]):
    def __init__(self, probability_for: float):
        self._p = probability_for

    def convert(self, judge: JudgeModel) -> Judge:
        return Judge(
            id=judge.id,
            is_president=judge.is_president,
            T_i="judge",
            P_i=judge.party.position,
            S_i=judge.influence,
            W=Weights(judge.weights),
            belief=AgentBelief(
                o_i=judge.personal_opinion,
                o_sup1=judge.appointing_group_opinion,
                o_sup2=judge.supporting_group_opinion,
            ),
        )


class CouncilDbAdapter(
    CouncilAdapter[int], RelatedInstitutionFinder[CourtModel], PrevVotesFinder
):
    @staticmethod
    def _build_network(judges: list[JudgeModel]) -> dict[int, list[int]]:
        return {to.id: [fro.id for fro in to.neighbours_in.all()] for to in judges}

    def convert(self, simulation_id: int) -> Council:
        value = Simulation.objects.get(pk=simulation_id)
        court = self._find_institution(value, CourtModel)
        judge_adapter = JudgeDbAdapter(court.probability_for)
        court_judges = list(
            court.judges.all().prefetch_related("court", "neighbours_in")
        )
        prev_votes = self._get_prev_votes(value, SubmodelType.JUDICIARY)
        return Council(
            judges=list(map(judge_adapter.convert, court_judges)),
            alpha=value.social_influence_susceptibility,
            epsilon=value.user_settings.abstention_threshold,
            gamma=value.office_retention_sensitivity,
            network=self._build_network(court_judges),
            prev_votes=prev_votes,
        )
