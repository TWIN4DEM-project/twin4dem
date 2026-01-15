from unittest.mock import ANY, call

import pytest
import pytest_asyncio


@pytest.fixture
def simulation_id(request):
    return int(getattr(request, "param", 1))


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
            serializer="pydantic",
        )
    ]


@pytest.mark.asyncio
async def test_government_step_event(
    sim_comm, load_json, get_channel_name, channel_layer
):
    payload = load_json("government/step_output.valid.json")
    await sim_comm.send_json_to({"action": "step"})
    await sim_comm.receive_json_from(timeout=0.1)

    await channel_layer.send(
        get_channel_name(),
        {"type": "government.step", "payload": payload},
    )
    actual = await sim_comm.receive_json_from(timeout=0.1)
    status = await sim_comm.receive_json_from(timeout=0.1)

    assert actual == payload
    assert status == {"status": "task completed"}
