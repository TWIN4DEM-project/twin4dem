from unittest.mock import ANY, call, patch, MagicMock

import pytest
import pytest_asyncio

from simulator.persistence import SimulationPersistence


@pytest.fixture
def simulation_id(request):
    return int(getattr(request, "param", 1))


@pytest.fixture
def persistence_mock():
    with patch("web.channels._simulation.get_simulation_persistence") as mock:
        mock.return_value = MagicMock(
            name="mock-persistence", spec=SimulationPersistence
        )
        yield mock.return_value


@pytest_asyncio.fixture
async def sim_comm(new_communicator, simulation_id, simulation_task_mock):
    c = new_communicator(f"ws/simulation/{simulation_id}/")
    try:
        await c.connect(timeout=0.1)
        yield c
    finally:
        await c.disconnect(timeout=0.1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "simulation_id,expected_message",
    [
        (1, "task 1 started"),
        (21, "task 21 started"),
    ],
    indirect=("simulation_id",),
)
async def test_simulation_started(
    sim_comm,
    simulation_id,
    simulation_task_mock,
    expected_message,
):
    await sim_comm.send_json_to({"action": "step"})

    response = await sim_comm.receive_json_from()

    assert response == {"status": expected_message}
    assert simulation_task_mock.apply_async.call_count == 1
    assert simulation_task_mock.apply_async.call_args_list == [
        call(
            args=[ANY],
            kwargs={"simulation_id": str(simulation_id), "data": ANY},
        )
    ]


@pytest.mark.asyncio
async def test_step_finished_event(
    persistence_mock, sim_comm, load_json, get_channel_name, channel_layer
):
    payload = load_json("events/step_finished.valid.json")
    await sim_comm.send_json_to({"action": "step"})
    await sim_comm.receive_json_from(timeout=0.1)

    await channel_layer.send(
        get_channel_name(),
        {"type": "step.finished", "payload": payload},
    )
    actual = await sim_comm.receive_json_from(timeout=0.1)
    status = await sim_comm.receive_json_from(timeout=0.1)

    assert actual == payload
    assert status == {"status": "task completed"}
    assert persistence_mock.persist_step.call_count == 1
    assert persistence_mock.persist_step.call_args_list == [call(payload)]
