from time import sleep

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from .model.config import GovernmentConfig
from .model.executive.government import Government


@shared_task
def count_to_ten(channel_name):
    layer = get_channel_layer()
    send = async_to_sync(layer.send)
    print(f"using {type(layer)} layer to communicate on channel {channel_name}")

    for i in range(1, 10):
        send(
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
    send = async_to_sync(layer.send)

    for _ in range(n_steps):
        step_result = gov.step()
        send(
            channel_name,
            {
                "type": "government.step",
                "payload": step_result,
            },
        )
