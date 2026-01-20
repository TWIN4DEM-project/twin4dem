import asyncio
import importlib

from asgiref.sync import async_to_sync
from celery import shared_task, chain
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction

from common.dto import SimulationStepResult, StepFinishedEvent
from common.models import Simulation
from .adapters import AdapterFactory


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


@shared_task(pydantic=True)
def send_result_to_channel(step_result: SimulationStepResult, channel_name: str):
    layer = get_channel_layer()
    finished_event = StepFinishedEvent(payload=step_result)
    serialized_event = finished_event.model_dump(mode="json", by_alias=True)

    with transaction.atomic():  # transactional outbox
        sim = Simulation.objects.get(pk=step_result.simulation_id)
        sim.current_step = step_result.step_no
        sim.save()
        send_sync(layer, channel_name, serialized_event)


@shared_task(pydantic=True)
def subsequent_submodel(step_result: SimulationStepResult):
    path = step_result.results[0].path
    factory = get_adapter_factory()
    if path == "decree":
        adapter = factory.new_council_adapter()
    else:
        adapter = factory.new_parliament_adapter()

    submodel = adapter.convert(step_result.simulation_id)
    result = submodel.step()
    step_result.results.append(result)

    return step_result.model_dump(mode="json", by_alias=True)


@shared_task(bind=True, pydantic=True)
def decide_and_dispatch(self, step_result: SimulationStepResult, channel_name: str):
    """
    Canvas-friendly conditional branching.

    This task replaces itself in the current canvas with either:
    - subsequent_submodel -> send_result_to_channel   (if approved), or
    - send_result_to_channel                          (if not approved)
    in order to ensure the proper submodel (or none) follow the executive
    sub-model's decision - as documented in the Toy Model v2.

    :param step_result: represents the result of the executive sub-model and is
        used as an input for deciding whether another sub-model is needed to
        assess the aggrandisement unit.
    :param channel_name: the name of the Django channel where the websocket
        router is listening
    """
    previous_step_result_json = step_result.model_dump(mode="json", by_alias=True)
    if step_result.results[-1].approved:
        workflow = chain(
            subsequent_submodel.s(previous_step_result_json),
            send_result_to_channel.s(channel_name),
        )
    else:
        workflow = send_result_to_channel.s(previous_step_result_json, channel_name)

    return self.replace(workflow)


@shared_task(pydantic=True)
def executive_submodel(step_result: SimulationStepResult):
    factory = get_adapter_factory()
    gov = factory.new_government_adapter().convert(step_result.simulation_id)
    cabinet_result = gov.step()
    step_result.results.append(cabinet_result)
    return step_result.model_dump(mode="json", by_alias=True)


@shared_task(pydantic=True)
def run_simulation(
    channel_name: str, simulation_id: int, step_count: int = 1, data=None
):
    simulation = Simulation.objects.get(pk=int(simulation_id))
    next_step = simulation.current_step + 1
    task_input = [
        SimulationStepResult(step_no=step_no, simulation_id=simulation_id, results=[])
        for step_no in range(next_step, next_step + step_count)
    ]
    workflows = []
    for step_input in task_input:
        step_json = step_input.model_dump(mode="json", by_alias=True)
        workflows.append(
            chain(
                executive_submodel.s(step_json),
                decide_and_dispatch.s(channel_name),
            )
        )
    chain(*workflows).apply_async()
