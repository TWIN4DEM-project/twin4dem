from time import sleep

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer


@shared_task
def count_to_ten(channel_name):
    layer = get_channel_layer()
    send = async_to_sync(layer.send)
    print(f"using {type(layer)} layer to communicate on channel {channel_name}")

    for i in range(1, 10):
        send(
            channel_name, {
                "type": "counter.update",
                "value": i,
            }
        )
        sleep(0.5)
