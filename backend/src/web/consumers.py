import json
from time import sleep

from channels.generic.websocket import WebsocketConsumer


class SimulationProgressConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()

    def disconnect(self, close_code):
        pass

    def receive(self, text_data: str | None = None, bytes_data: bytes | None = None):
        i = 0
        while i < 10:
            self.send(text_data=json.dumps({"counter": i}))
            sleep(1.0)
            i += 1