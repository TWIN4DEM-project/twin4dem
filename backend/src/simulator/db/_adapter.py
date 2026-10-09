import random
from collections import Counter
from collections.abc import Iterable
from typing import Any, TypeVar

from django.db import models

from common.models import (
    Simulation,
    SimulationInstitution,
    SerializationModel,
    PartyPositionType,
    party_position_at,
    Minister as MinisterModel,
    MemberOfParliament,
    Judge as JudgeModel,
    MinisterBelief,
    MPBelief,
    JudgeBelief,
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


def _effective(override: float | None, default: float) -> float:
    """An institution's probability override, or the user settings default."""
    return default if override is None else override


TBelief = TypeVar("TBelief", bound=models.Model)


class RelatedInstitutionFinder:
    @classmethod
    def _find_institution(
        cls, simulation: Simulation, serialization_model: str
    ) -> SimulationInstitution | None:
        return (
            simulation.institutions.filter(
                institution__serialization_model=serialization_model
            )
            .select_related("institution")
            .first()
        )

    @classmethod
    def _get_institution(
        cls, simulation: Simulation, serialization_model: str
    ) -> SimulationInstitution:
        result = cls._find_institution(simulation, serialization_model)
        if result is None:
            raise ValueError(
                f"there is no {serialization_model} in simulation {simulation.id}"
            )
        return result


class PartyPositionFinder(RelatedInstitutionFinder):
    @classmethod
    def _get_party_positions(
        cls, simulation: Simulation, party_ids: Iterable[int]
    ) -> dict[int, str]:
        """
        The position (majority, opposition, independent) of each party in the
        simulation's chamber at the simulated point in time. Parties without a
        position there, or simulations without a chamber, count as independent.
        """
        party_ids = set(party_ids)
        chamber = cls._find_institution(simulation, SerializationModel.CHAMBER)
        if chamber is None:
            return {party_id: PartyPositionType.INDEPENDENT for party_id in party_ids}
        result = {}
        for party_id in party_ids:
            party_position = party_position_at(
                party_id, chamber.institution, simulation.timeline, simulation.valid_at
            )
            result[party_id] = (
                party_position.position
                if party_position is not None
                else PartyPositionType.INDEPENDENT
            )
        return result


class StepBeliefsFinder:
    @staticmethod
    def _get_beliefs_for_step(
        belief_model: type[TBelief],
        simulation_id: int,
        step_no: int | None,
    ) -> dict[int, TBelief]:
        if step_no is None:
            return {}
        return {
            belief.agent_id: belief
            for belief in belief_model.objects.filter(
                unit__batch__simulation_id=simulation_id,
                unit__step_no=step_no,
            ).select_related("agent", "unit")
        }


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
    def __init__(
        self,
        beliefs_for_step: dict[int, MinisterBelief] | None = None,
        party_positions: dict[int, str] | None = None,
    ):
        self._beliefs_for_step = beliefs_for_step or {}
        self._party_positions = party_positions or {}

    def convert(self, value: MinisterModel) -> Minister:
        step_belief = self._beliefs_for_step.get(value.id)

        return Minister(
            id=value.id,
            T_i="Minister",
            is_pm=value.is_prime_minister,
            P_i=self._party_positions.get(
                value.party_id, PartyPositionType.INDEPENDENT
            ),
            S_i=value.influence,
            W=Weights(value.weights),
            belief=AgentBelief(
                o_i=(
                    step_belief.personal_opinion
                    if step_belief is not None
                    else value.personal_opinion
                ),
                # support group 1 = ones who have the power to affect the status of the minister (appoint, revoke, etc)
                o_sup1=(
                    step_belief.appointing_group_opinion
                    if step_belief is not None
                    else value.appointing_group_opinion
                ),
                # support group 2 = people who are directly benefitting from ministers getting more power
                # setting this to 1.0 until better ideas about how to compute this value emerge
                o_sup2=(
                    step_belief.supporting_group_opinion
                    if step_belief is not None
                    else value.supporting_group_opinion
                ),
            ),
        )


class GovernmentDbAdapter(
    GovernmentAdapter[int],
    PartyPositionFinder,
    PrevVotesFinder,
    StepBeliefsFinder,
):

    @staticmethod
    def _build_network(ministers: list[MinisterModel]) -> dict[int, list[int]]:
        return {
            minister.id: [n.id for n in minister.neighbours_in.all()]
            for minister in ministers
        }

    def convert(self, simulation_id: int, **kwargs: Any) -> Government:
        value = Simulation.objects.select_related("user_settings", "timeline").get(
            pk=simulation_id
        )
        step_no = kwargs.get("step_no")
        beliefs_for_step = self._get_beliefs_for_step(
            MinisterBelief, simulation_id, step_no
        )
        cabinet = self._get_institution(value, SerializationModel.CABINET)
        minister_models = list(
            cabinet.ministers.all().prefetch_related("neighbours_in")
        )
        minister_adapter = MinisterDbAdapter(
            beliefs_for_step=beliefs_for_step,
            party_positions=self._get_party_positions(
                value, (minister.party_id for minister in minister_models)
            ),
        )
        ministers = list(map(minister_adapter.convert, minister_models))
        previous_votes = self._get_prev_votes(value, SubmodelType.EXECUTIVE)

        return Government(
            # the cabinet's legislative path probability is a global parameter now
            pact=value.user_settings.legislative_path_probability,
            alpha=value.social_influence_susceptibility,
            gamma=value.office_retention_sensitivity,
            epsilon=value.user_settings.abstention_threshold,
            ministers=ministers,
            network=self._build_network(minister_models),
            previous_votes=previous_votes,
        )


class MPDbAdapter(AgentAdapter[MemberOfParliament, MP]):
    def __init__(
        self,
        majority_prob_for: float,
        opposition_prob_for: float,
        beliefs_for_step: dict[int, MPBelief] | None = None,
    ):
        self._majority_for = majority_prob_for
        self._opposition_for = opposition_prob_for
        self._beliefs_for_step = beliefs_for_step or {}

    def convert(self, mp: MemberOfParliament) -> MP:
        step_belief = self._beliefs_for_step.get(mp.id)
        return MP(
            id=mp.id,
            T_i="mp",
            P_i=mp.party.label,
            W=Weights(mp.weights),
            is_head=mp.is_head,
            S_i=0,
            belief=AgentBelief(
                o_i=(
                    step_belief.personal_opinion
                    if step_belief is not None
                    else mp.personal_opinion
                ),
                o_sup1=(
                    step_belief.appointing_group_opinion
                    if step_belief is not None
                    else mp.appointing_group_opinion
                ),
                o_sup2=(
                    step_belief.supporting_group_opinion
                    if step_belief is not None
                    else mp.supporting_group_opinion
                ),
            ),
        )


class ParliamentDbAdapter(
    ParliamentAdapter[int],
    RelatedInstitutionFinder,
    PrevVotesFinder,
    StepBeliefsFinder,
):

    def convert(self, simulation_id: int, **kwargs: Any) -> Parliament:
        value = Simulation.objects.select_related("user_settings").get(pk=simulation_id)
        step_no = kwargs.get("step_no")
        beliefs_for_step = self._get_beliefs_for_step(MPBelief, simulation_id, step_no)
        chamber = self._get_institution(value, SerializationModel.CHAMBER)
        chamber_members = list(
            chamber.members.all().select_related("party").order_by("id")
        )
        payload = chamber.institution.get_payload()
        mp_adapter = MPDbAdapter(
            _effective(
                payload.majority_probability_for,
                value.user_settings.parliament_majority_probability_for,
            ),
            _effective(
                payload.opposition_probability_for,
                value.user_settings.parliament_opposition_probability_for,
            ),
            beliefs_for_step=beliefs_for_step,
        )
        mps = list(map(mp_adapter.convert, chamber_members))
        previous_votes = self._get_prev_votes(value, SubmodelType.LEGISLATIVE)
        # seats per party, in the order the parties first appear among the MPs
        seats = Counter(mp.party_id for mp in chamber_members)
        return Parliament(
            mps=mps,
            n_party=len(seats),
            n_sits=list(seats.values()),
            alpha=value.social_influence_susceptibility,
            epsilon=value.user_settings.abstention_threshold,
            gamma=value.office_retention_sensitivity,
            prev_votes=previous_votes,
        )


class JudgeDbAdapter(AgentAdapter[JudgeModel, Judge]):
    def __init__(
        self,
        probability_for: float,
        beliefs_for_step: dict[int, JudgeBelief] | None = None,
        party_positions: dict[int, str] | None = None,
    ):
        self._p = probability_for
        self._beliefs_for_step = beliefs_for_step or {}
        self._party_positions = party_positions or {}

    def convert(self, judge: JudgeModel) -> Judge:
        step_belief = self._beliefs_for_step.get(judge.id)
        return Judge(
            id=judge.id,
            is_president=judge.is_president,
            T_i="judge",
            P_i=self._party_positions.get(
                judge.party_id, PartyPositionType.INDEPENDENT
            ),
            S_i=judge.influence,
            W=Weights(judge.weights),
            belief=AgentBelief(
                o_i=(
                    step_belief.personal_opinion
                    if step_belief is not None
                    else judge.personal_opinion
                ),
                o_sup1=(
                    step_belief.appointing_group_opinion
                    if step_belief is not None
                    else judge.appointing_group_opinion
                ),
                o_sup2=(
                    step_belief.supporting_group_opinion
                    if step_belief is not None
                    else judge.supporting_group_opinion
                ),
            ),
        )


class CouncilDbAdapter(
    CouncilAdapter[int],
    PartyPositionFinder,
    PrevVotesFinder,
    StepBeliefsFinder,
):
    @staticmethod
    def _build_network(judges: list[JudgeModel]) -> dict[int, list[int]]:
        return {to.id: [fro.id for fro in to.neighbours_in.all()] for to in judges}

    def convert(self, simulation_id: int, **kwargs: Any) -> Council:
        value = Simulation.objects.select_related("user_settings", "timeline").get(
            pk=simulation_id
        )
        step_no = kwargs.get("step_no")
        beliefs_for_step = self._get_beliefs_for_step(
            JudgeBelief, simulation_id, step_no
        )
        court = self._get_institution(value, SerializationModel.COURT)
        court_judges = list(court.judges.all().prefetch_related("neighbours_in"))
        judge_adapter = JudgeDbAdapter(
            _effective(
                court.institution.get_payload().probability_for,
                value.user_settings.court_probability_for,
            ),
            beliefs_for_step=beliefs_for_step,
            party_positions=self._get_party_positions(
                value, (judge.party_id for judge in court_judges)
            ),
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
