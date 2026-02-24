from random import random
from unittest.mock import patch, call, ANY

import pytest

from common.models import (
    SimulationLogEntry,
    SimulationSubmodelLogEntry,
    SubmodelType,
    PathSubmodelInfo,
    Cabinet,
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