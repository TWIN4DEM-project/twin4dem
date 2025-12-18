import asyncio
import importlib

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings

from .adapters import AdapterFactory
from .config import GovernmentConfig, ConfigAdapters


def send_sync(layer, channel_name, data):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        send = async_to_sync(layer.send)
        send(channel_name, data)
    else:
        return loop.create_task(layer.send(channel_name, data))


def get_adapter_factory() -> AdapterFactory:
    fqcn = getattr(settings, "ADAPTER_FACTORY")
    last_dot_idx = fqcn.rindex(".")
    module_name = fqcn[:last_dot_idx]
    class_name = fqcn[last_dot_idx+1:]
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return cls()


@shared_task
def run_government_steps(channel_name: str, data: GovernmentConfig, n_steps: int = 1):
    factory = get_adapter_factory()
    gov = factory.new_government_adapter().convert(data)
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
