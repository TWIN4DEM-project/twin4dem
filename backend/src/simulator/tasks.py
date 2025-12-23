import asyncio
import importlib

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings

from .adapters import AdapterFactory
from .config import GovernmentConfig, ParliamentConfig


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
    class_name = fqcn[last_dot_idx + 1 :]
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return cls()


@shared_task
def run_legislative_steps(channel_name: str, data: ParliamentConfig):
    factory = get_adapter_factory()
    parl = factory.new_parliament_adapter().convert(data)
    layer = get_channel_layer()

    parl_step_result = parl.step()

    send_sync(
        layer,
        channel_name,
        {
            "type": "parliament.step",
            "payload": parl_step_result,
        },
    )


@shared_task
def run_government_steps(
    channel_name: str,
    simulation_id: int | None = None,
    data: GovernmentConfig | None = None,
    parl_data: ParliamentConfig | None = None,
    n_steps: int = 1,
):
    factory = get_adapter_factory()
    gov = factory.new_government_adapter().convert(simulation_id or data)
    layer = get_channel_layer()

    for _ in range(n_steps):
        step_result = gov.step()

        approved = bool(step_result.get("approved"))
        path = step_result.get("path")  # "legislative act" | "decree" | None

        send_sync(
            layer,
            channel_name,
            {
                "type": "government.step",
                "payload": step_result,
            },
        )

        if approved and path == "legislative act":
            if parl_data is None:
                continue

            run_legislative_steps.apply_async(args=[channel_name, parl_data])
        else:
            send_sync(
                layer,
                channel_name,
                {
                    "type": "government.step",
                    "payload": step_result,
                },
            )
