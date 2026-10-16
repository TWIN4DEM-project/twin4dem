from random import random
from unittest.mock import patch, call, ANY

import pytest

from common.models import (
    InstitutionBranch,
    SimulationLogEntry,
    SimulationSubmodelLogEntry,
    SubmodelType,
    PathSubmodelInfo,
    MinisterBelief,
    PartyPositionType,
    SimulationInstitution,
)
import simulator.db._adapter as adapter_module
from simulator.db import GovernmentDbAdapter


@pytest.fixture
def previous_votes(simulation, cabinet):
    # randomize votes per test call
    result = {
        str(minister.id): int(random() > 0.75) for minister in cabinet.ministers.all()
    }
    log_entry = SimulationLogEntry.objects.create(
        simulation=simulation,
        approved=False,
        step_no=1,
        last_decision_type=SubmodelType.EXECUTIVE,
        aggrandisement_path=None,
    )
    SimulationSubmodelLogEntry.objects.create(
        log_entry=log_entry,
        submodel_type=SubmodelType.EXECUTIVE,
        approved=False,
        additional_info=PathSubmodelInfo(path=None, votes=result),
    )
    return result


@pytest.fixture
def executive_submodel_mock():
    with patch("simulator.db._adapter.Government") as mock:
        yield mock


@pytest.fixture
def sut():
    return GovernmentDbAdapter()


def test_government_db_adapter_init_submodel_with_expected_params(
    sut, simulation, cabinet, previous_votes, executive_submodel_mock
):
    sut.convert(simulation.id)

    assert executive_submodel_mock.call_count == 1
    assert executive_submodel_mock.call_args_list == [
        call(
            pact=simulation.user_settings.legislative_path_probability,
            alpha=simulation.social_influence_susceptibility,
            gamma=simulation.office_retention_sensitivity,
            epsilon=simulation.user_settings.abstention_threshold,
            ministers=ANY,
            network=ANY,
            previous_votes=previous_votes,
        )
    ]


def test_government_db_adapter_init_submodel_without_prev_results(
    sut, simulation, cabinet, executive_submodel_mock
):
    sut.convert(simulation.id)

    assert executive_submodel_mock.call_count == 1
    assert executive_submodel_mock.call_args_list == [
        call(
            pact=simulation.user_settings.legislative_path_probability,
            alpha=simulation.social_influence_susceptibility,
            gamma=simulation.office_retention_sensitivity,
            epsilon=simulation.user_settings.abstention_threshold,
            ministers=ANY,
            network=ANY,
            previous_votes={},
        )
    ]


def test_minister_personal_opinion_stable_across_conversions(
    sut, simulation, monkeypatch
):
    phase = {"value": 0.9}

    def fake_random_gauss(center, spread=1.0, lo=0.0, hi=1.0):
        return phase["value"]

    monkeypatch.setattr(adapter_module, "_random_gauss", fake_random_gauss)

    gov_first = sut.convert(simulation.id)
    opinions_first = {m.id: m.belief.o_i for m in gov_first.ministers}

    phase["value"] = 0.1
    gov_second = sut.convert(simulation.id)
    opinions_second = {m.id: m.belief.o_i for m in gov_second.ministers}

    assert opinions_first == opinions_second


@pytest.fixture
def step_no():
    return 3


@pytest.fixture
def aggrandisement_unit(simulation, step_no, make_aggrandisement_unit):
    return make_aggrandisement_unit(simulation, step_no)


@pytest.fixture
def targeted_and_fallback(cabinet):
    ministers = list(cabinet.ministers.all().order_by("id"))
    assert len(ministers) >= 2
    return ministers[0], ministers[1]


@pytest.fixture
def minister_step_belief(aggrandisement_unit, configured_global_beliefs):
    targeted, _ = configured_global_beliefs
    return MinisterBelief.objects.create(
        unit=aggrandisement_unit,
        agent=targeted,
        personal_opinion=1.0,
        appointing_group_opinion=1.0,
        supporting_group_opinion=1.0,
    )


@pytest.mark.django_db
def test_convert_uses_step_specific_minister_beliefs_with_global_fallback(
    sut, simulation, step_no, configured_global_beliefs, minister_step_belief
):
    targeted, fallback = configured_global_beliefs
    government = sut.convert(simulation.id, step_no=step_no)
    converted = {m.id: m for m in government.ministers}

    assert converted[targeted.id].belief.o_i == 1.0
    assert converted[targeted.id].belief.o_sup1 == 1.0
    assert converted[targeted.id].belief.o_sup2 == 1.0

    assert converted[fallback.id].belief.o_i == fallback.personal_opinion
    assert converted[fallback.id].belief.o_sup1 == fallback.appointing_group_opinion
    assert converted[fallback.id].belief.o_sup2 == fallback.supporting_group_opinion


@pytest.mark.django_db
def test_ministers_are_independent_without_chamber(sut, simulation):
    government = sut.convert(simulation.id)

    assert {m.P_i for m in government.ministers} == {PartyPositionType.INDEPENDENT}


@pytest.mark.django_db
@pytest.mark.parametrize("simulation_id", [2], indirect=True)
def test_ministers_take_party_position_in_simulated_chamber(sut, simulation):
    # world.json: party 1 is in the majority and party 2 in the opposition
    SimulationInstitution.objects.create(simulation=simulation, institution_id=2)

    government = sut.convert(simulation.id)

    party_ids = dict(
        simulation.institutions.get(
            institution__kind__branch=InstitutionBranch.EXECUTIVE
        ).ministers.values_list("id", "party_id")
    )
    expected = {1: "majority", 2: "opposition"}
    assert {m.id: m.P_i for m in government.ministers} == {
        minister_id: expected[party_id] for minister_id, party_id in party_ids.items()
    }
