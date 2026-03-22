import asyncio
from unittest.mock import MagicMock, call

import celery
import pytest
import pytest_asyncio
from channels.routing import URLRouter
from django.urls import re_path

from web.channels._base_consumer import Twin4DemAsyncConsumer


DEFAULT_TEST_ROUTE = "basic-test-route/"


class StubConsumer(Twin4DemAsyncConsumer):
    def __init__(
        self,
        task_mock: MagicMock,
        on_started: MagicMock,
        done: asyncio.Event,
        *args,
        **kwargs,
    ):
        super().__init__(task_mock, *args, **kwargs)
        self._startup_mock = on_started
        self._startup_failed_mock = MagicMock()
        self._done = done

    async def receive(self, text_data=None, bytes_data=None):
        try:
            self._done.clear()
            return await super().receive(text_data, bytes_data)
        finally:
            self._done.set()

    async def _can_run_task(self, *args, **kwargs) -> bool:
        return True

    async def _on_task_cannot_start(self):
        self._startup_failed_mock()

    async def _on_task_started(self):
        self._startup_mock()


@pytest.fixture
def done_event():
    return asyncio.Event()


@pytest.fixture
def task_mock():
    return MagicMock(name="mock task", spec=celery.Task)


@pytest.fixture
def start_mock():
    return MagicMock(name="on_start")


@pytest.fixture
def stub_asgi_app(task_mock, start_mock, done_event):
    return StubConsumer.as_asgi(
        task_mock=task_mock, on_started=start_mock, done=done_event
    )


@pytest.fixture
def path(request):
    return getattr(request, "param", DEFAULT_TEST_ROUTE)


@pytest.fixture
def url_router(request, stub_asgi_app, path):
    url_pattern = getattr(request, "param", path)
    return URLRouter([re_path(url_pattern, stub_asgi_app)])


@pytest_asyncio.fixture
async def stub_comm(new_communicator, stub_asgi_app, path, url_router):
    c = new_communicator(f"ws://some-server/{path}", url_router)
    try:
        await c.connect(timeout=0.1)
        yield c
    finally:
        await c.disconnect(timeout=0.1)


@pytest.mark.asyncio
async def test_base_consumer_specifies_channel_name(stub_comm, task_mock, done_event):
    await stub_comm.send_json_to({})
    await done_event.wait()
    assert task_mock.apply_async.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,url_router,expected_args,expected_kwargs",
    [
        ("path/without/anything/", "path/without/anything/", [], {}),
        ("unnamed/param/1/", "unnamed/param/(\d+)/", ["1"], {}),
        ("named/param/1/", "named/param/(?P<id>\d+)/", [], {"id": "1"}),
    ],
    indirect=("path", "url_router"),
)
async def test_base_consumer_passes_url_params_to_task(
    stub_comm, task_mock, expected_args, expected_kwargs, done_event
):
    await stub_comm.send_json_to({})
    await done_event.wait()

    call_args = task_mock.apply_async.call_args[1]
    args = call_args["args"][1:]
    kwargs = call_args["kwargs"]
    kwargs.pop("data")

    assert args == expected_args
    assert kwargs == expected_kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data",
    [
        {},
        {"a": "dict"},
    ],
)
async def test_base_consumer_passes_data(stub_comm, task_mock, data, done_event):
    await stub_comm.send_json_to(data)
    await done_event.wait()

    call_args = task_mock.apply_async.call_args[1]
    kwargs = call_args["kwargs"]
    actual = kwargs.pop("data")

    assert actual == data


@pytest.mark.asyncio
async def test_base_consumer_startup_callback_is_called(
    stub_comm, start_mock, done_event
):
    await stub_comm.send_json_to({})
    await done_event.wait()

    assert start_mock.call_count == 1
    assert start_mock.call_args_list == [call()]
