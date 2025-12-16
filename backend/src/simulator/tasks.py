import asyncio

from time import sleep

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from .model.config import GovernmentConfig
from .model.executive.government import Government


def send_sync(layer, channel_name, data):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        send = async_to_sync(layer.send)
        send(channel_name, data)
    else:
        return loop.create_task(layer.send(channel_name, data))


@shared_task
def count_to_ten(channel_name):
    layer = get_channel_layer()

    for i in range(1, 10):
        send_sync(
            layer,
            channel_name,
            {
                "type": "counter.update",
                "value": i,
            },
        )
        sleep(0.5)


@shared_task
def run_government_steps(channel_name: str, data: GovernmentConfig, n_steps: int = 1):
    gov = Government.from_config(data)
    layer = get_channel_layer()

    for _ in range(n_steps):
        step_result = gov.step()
        send_sync(
            layer,
            channel_name,
            {
                "type": "government.step",
                "payload": step_result,
            },
        )
