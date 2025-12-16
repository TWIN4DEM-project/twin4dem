import json
from typing import Callable

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
async def communicator(application, request):
    simulation_id = int(request.param) if hasattr(request, "param") else 1
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
    "communicator,expected_message",
    [
        (1, "task 1 started"),
        (21, "task 21 started"),
    ],
    indirect=("communicator",),
)
async def test_simulation_started(communicator, load_pydantic, expected_message):
    await communicator.send_to(text_data=json.dumps(load_pydantic("scenario1.json")))

    response = await communicator.receive_from()
    response = json.loads(response)

    assert response == {"status": expected_message}


@pytest.mark.anyio
async def test_simulation_id(communicator, load_pydantic):
    await communicator.connect()
    await communicator.send_to(text_data=json.dumps(load_pydantic("scenario1.json")))
    await communicator.receive_from()

    response = await communicator.receive_from()
    response = json.loads(response)

    assert isinstance(response, dict)
    assert "t" in response
    assert "approved" in response
    assert "path" in response
    assert "votes" in response
