import json

from celery import Task
from channels.generic.websocket import AsyncWebsocketConsumer

from simulator.tasks import count_to_ten, run_government_steps


class Twin4DemAsyncConsumer(AsyncWebsocketConsumer):
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
        self._task.apply_async(args=[self.channel_name], kwargs=task_args, serializer="pydantic")
        await self._send_json({"status": "task started"})

    async def _send_json(self, obj):
        await self.send(text_data=json.dumps(obj))


class SimulationProgressConsumer(Twin4DemAsyncConsumer):
    def __init__(self):
        super().__init__(count_to_ten)


class ExecutiveModelConsumer(Twin4DemAsyncConsumer):
    def __init__(self):
        super().__init__(run_government_steps)

    async def government_step(self, event):
        await self._send_json(event["payload"])
        await self._send_json({"status": "task completed"})
