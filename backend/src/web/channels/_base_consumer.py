import json
from abc import ABCMeta, abstractmethod

from celery import Task
from channels.generic.websocket import AsyncWebsocketConsumer


class Twin4DemAsyncConsumer(AsyncWebsocketConsumer, metaclass=ABCMeta):
    def __init__(self, task: Task, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._task = task

    async def connect(self):
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        # we don't support gzip compression, msgpack, protobuf or avro for now
        url_route = self.scope.get("url_route", {})
        task_kwargs = url_route.get("kwargs", {})
        if text_data is not None:
            task_kwargs.update(dict(data=json.loads(text_data)))
        task_args = [self.channel_name, *url_route.get("args", [])]
        self._task.apply_async(
            args=task_args, kwargs=task_kwargs, serializer="pydantic"
        )
        await self._on_task_started()

    @abstractmethod
    async def _on_task_started(self):
        pass

    async def _send_json(self, obj):
        await self.send(text_data=json.dumps(obj))
