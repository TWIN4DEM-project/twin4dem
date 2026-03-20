from random import random
from unittest.mock import patch, call, ANY

import pytest
from django.utils import timezone

from common.models import (
    SimulationLogEntry,
    SimulationSubmodelLogEntry,
    SubmodelType,
    PathSubmodelInfo,
    Cabinet,
    AggrandisementBatch,
    AggrandisementUnit,
    MinisterBelief,
)
import simulator.db._adapter as adapter_module
from simulator.db import GovernmentDbAdapter


@pytest.fixture
def cabinet(simulation, institution_params):
    return institution_params(simulation, Cabinet)


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
            pact=cabinet.legislative_probability,
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
            pact=cabinet.legislative_probability,
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
def aggrandisement_unit(simulation, step_no):
    batch = AggrandisementBatch.objects.create(
        simulation=simulation,
        start_date=timezone.now(),
        end_date=timezone.now(),
    )
    return AggrandisementUnit.objects.create(batch=batch, step_no=step_no)


@pytest.fixture
def targeted_and_fallback_ministers(cabinet):
    ministers = list(cabinet.ministers.all().order_by("id"))
    assert len(ministers) >= 2
    return ministers[0], ministers[1]


@pytest.fixture
def configured_global_beliefs(targeted_and_fallback_ministers):
    targeted, fallback = targeted_and_fallback_ministers
    targeted.personal_opinion = 0.0
    targeted.appointing_group_opinion = 0.0
    targeted.supporting_group_opinion = 0.0
    targeted.save(
        update_fields=[
            "personal_opinion",
            "appointing_group_opinion",
            "supporting_group_opinion",
        ]
    )
    fallback.personal_opinion = 1.0
    fallback.appointing_group_opinion = 1.0
    fallback.supporting_group_opinion = 1.0
    fallback.save(
        update_fields=[
            "personal_opinion",
            "appointing_group_opinion",
            "supporting_group_opinion",
        ]
    )
    return targeted, fallback


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
