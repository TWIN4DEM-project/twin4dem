import json
from typing import Callable
from unittest.mock import patch, ANY, call

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.urls import re_path

from web.channels import SimulationAsyncConsumer


@pytest.fixture
def application():
    return URLRouter(
        [
            re_path(
                r"ws/simulation/(?P<simulation_id>\d+)/$",
                SimulationAsyncConsumer.as_asgi(),
            ),
        ]
    )


@pytest.fixture
def task_mock():
    with patch("web.channels._simulation.run_government_steps") as mock:
        yield mock


@pytest.fixture
def simulation_id(request):
    return int(request.param) if hasattr(request, "param") else 1


@pytest.fixture
async def communicator(application, simulation_id, task_mock):
    comm = WebsocketCommunicator(
        application, f"ws://localhost:8000/ws/simulation/{simulation_id}/"
    )
    await comm.connect()
    yield comm
    await comm.disconnect()


@pytest.fixture
def load_pydantic(load_json) -> Callable[[str], dict]:
    def _(filename: str) -> dict:
        return {
            "__pydantic_model__": "GovernmentConfig",
            "data": load_json(filename),
        }

    return _


@pytest.mark.anyio
@pytest.mark.parametrize(
    "simulation_id,expected_message",
    [
        (1, "task 1 started"),
        (21, "task 21 started"),
    ],
    indirect=("simulation_id",),
)
async def test_simulation_started(
    simulation_id, communicator, load_pydantic, expected_message, task_mock
):
    await communicator.send_to(text_data=json.dumps(load_pydantic("scenario1.json")))

    response = await communicator.receive_from()
    response = json.loads(response)

    assert response == {"status": expected_message}
    assert task_mock.apply_async.call_count == 1
    assert task_mock.apply_async.call_args_list == [
        call(
            args=[ANY],
            kwargs={"simulation_id": str(simulation_id), "data": ANY},
            serializer="pydantic",
        )
    ]
