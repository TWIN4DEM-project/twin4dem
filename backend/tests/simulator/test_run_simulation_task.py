from unittest.mock import patch, call

import pytest
from celery import Task

from simulator.tasks import run_simulation, executive_submodel, decide_and_dispatch


TEST_CHANNEL = "test-channel"


@pytest.fixture
def chain_mock():
    with patch("simulator.tasks.chain", spec=Task) as mock:
        yield mock


@pytest.mark.parametrize("current_step,step_count", [(1, 1), (3, 2), (7, 5)])
def test_run_n_simulations_creates_expected_chains(
    simulation, chain_mock, current_step, step_count
):
    simulation.current_step = current_step
    simulation.save()
    expected_calls = []
    for step_no in range(step_count):
        next_step = simulation.current_step + step_no + 1
        step_input = {"stepNo": next_step, "simulationId": simulation.id, "results": []}
        expected_calls.append(
            call(executive_submodel.s(step_input), decide_and_dispatch.s(TEST_CHANNEL))
        )
    expected_chain_calls = [chain_mock.return_value] * step_count
    expected_calls.append(call(*expected_chain_calls))

    run_simulation.delay(TEST_CHANNEL, simulation.id, step_count)

    assert chain_mock.call_args_list == expected_calls
