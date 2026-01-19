import asyncio
import importlib

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings

from .adapters import AdapterFactory
from .config import GovernmentConfig, ParliamentConfig, CouncilConfig


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
def run_judiciary_steps(simulation_id: int | None = None, data: CouncilConfig | None = None):
    factory = get_adapter_factory()

    if simulation_id is not None:
        council = factory.new_council_adapter().convert(simulation_id)
    else:
        council = factory.new_council_adapter().convert(data)

    council_step_result = council.step()

    return {
        "type": "court",
        **council_step_result,
    }


@shared_task
def run_legislative_steps(simulation_id: int | None = None, data: ParliamentConfig | None = None):
    factory = get_adapter_factory()

    if simulation_id is not None:
        parl = factory.new_parliament_adapter().convert(simulation_id)
    else:
        parl = factory.new_parliament_adapter().convert(data)

    parl_step_result = parl.step()

    return {
        "type": "parliament",
        **parl_step_result,
    }


@shared_task
def run_government_steps(
    channel_name: str,
    simulation_id: int | None = None,
    data: GovernmentConfig | None = None,
    parl_data: ParliamentConfig | None = None,
    council_data: CouncilConfig | None = None,
    n_steps: int = 1,
):
    factory = get_adapter_factory()
    gov = factory.new_government_adapter().convert(simulation_id or data)
    layer = get_channel_layer()

    for step in range(n_steps):
        step_result = {"t": step, "results": []}
        cabinet_result = gov.step()
        results = [{"type": "cabinet", **cabinet_result}]

        approved = bool(cabinet_result.get("approved"))
        path = cabinet_result.get("path")  # "legislative act" | "decree" | None

        if approved:
            task = None
            fallback_data = None

            match path:
                case "legislative act":
                    task = run_legislative_steps
                    fallback_data = parl_data
                case "decree":
                    task = run_judiciary_steps
                    fallback_data = council_data
                case _:
                    raise ValueError(f"unexpected path '{path}'")

            kwargs = None
            if simulation_id is not None:
                kwargs = {"simulation_id": simulation_id}
            elif fallback_data is not None:
                kwargs = {"data": fallback_data}

            if kwargs is not None:
                async_result = task.apply_async(kwargs=kwargs)
                try:
                    results.append(
                        async_result.get(timeout=300, disable_sync_subtasks=False)
                    )
                except TimeoutError:
                    pass  # introduce logging or implement conditional task chains

        step_result["results"] = results
        send_sync(
            layer, channel_name, {"type": "step.finished", "payload": step_result}
        )
