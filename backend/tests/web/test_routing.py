import pytest


@pytest.mark.asyncio
async def test_simulation_existing_route(new_communicator, simulation_task_mock):
    comm = new_communicator("ws://localhost:8000/ws/simulation/1/")

    try:
        await comm.connect()
        await comm.send_json_to({"action": "start"})
        response = await comm.receive_json_from()
    finally:
        await comm.disconnect()

    assert "status" in response
    assert simulation_task_mock.apply_async.call_count == 1


@pytest.mark.parametrize(
    "path",
    [
        "",
        "ws/simulation/1",
        "ws/simulation/1/2",
    ],
)
@pytest.mark.asyncio
async def test_simulation_non_existing_route(new_communicator, path):
    comm = new_communicator(f"ws://anything-really/{path}")
    with pytest.raises(Exception) as err_proxy:
        await comm.connect(timeout=0.1)

    assert str(err_proxy.value) == f"No route found for path '{path}'."
