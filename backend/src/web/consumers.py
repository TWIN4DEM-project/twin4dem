import json

from channels.generic.websocket import AsyncWebsocketConsumer

from simulator.tasks import count_to_ten


class SimulationProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def receive(self, text_data):
        print("received data")
        data = json.loads(text_data)

        # launch Celery task
        count_to_ten.delay(self.channel_name)
        print("started celery task")
        await self.send_json({"status": "counter started"})
        print("sent counter started event")

    async def counter_update(self, event):
        # automatically called on "counter.update" events received on this channel
        print("received event from celery task")
        await self.send_json({"counter": event["value"]})

    async def send_json(self, obj):
        await self.send(text_data=json.dumps(obj))
