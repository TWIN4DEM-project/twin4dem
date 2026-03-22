from typing import Callable, AsyncGenerator, Optional
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator

from simulator.persistence import SimulationPersistence
from web import routing


@pytest.fixture
def url_router() -> URLRouter:
    return URLRouter(routing.websocket_urlpatterns)


@pytest.fixture
def simulation_task_mock():
    with patch("web.channels._simulation.run_simulation") as mock:
        yield mock


@pytest.fixture(autouse=True)
def persistence_mock():
    with patch("web.channels._simulation.get_simulation_persistence") as mock:
        mock.return_value = MagicMock(
            name="mock-persistence", spec=SimulationPersistence
        )
        mock.return_value.can_perform_step.return_value = True
        yield mock.return_value


@pytest.fixture
def get_channel_name(simulation_task_mock):
    return lambda: simulation_task_mock.apply_async.call_args.kwargs["args"][0]


@pytest.fixture
def new_communicator(url_router) -> Callable[[...], WebsocketCommunicator]:
    def _communicator_factory(
        path: str, router: Optional[URLRouter] = None
    ) -> WebsocketCommunicator:
        if router is None:
            router = url_router
        return WebsocketCommunicator(router, path)

    return _communicator_factory


@pytest_asyncio.fixture
async def communicator(
    new_communicator, request
) -> AsyncGenerator[WebsocketCommunicator, None]:
    if not hasattr(request, "param"):
        raise AssertionError("communicator fixture expects parameters")
    if not isinstance(request.param, str):
        raise AssertionError("communicator fixture must be parametrized with a str")
    communicator = new_communicator(request.param)
    try:
        await communicator.connect()
        yield communicator
    finally:
        await communicator.disconnect()
