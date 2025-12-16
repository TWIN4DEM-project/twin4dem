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
        task_args = {}
        if text_data is not None:
            task_args = dict(data=json.loads(text_data))
        # launch Celery task
        self._task.apply_async(
            args=[self.channel_name], kwargs=task_args, serializer="pydantic"
        )
        await self._on_task_started()

    @abstractmethod
    async def _on_task_started(self):
        pass

    async def _send_json(self, obj):
        await self.send(text_data=json.dumps(obj))
