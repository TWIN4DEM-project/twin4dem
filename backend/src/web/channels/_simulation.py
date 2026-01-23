from simulator.persistence import get_simulation_persistence
from channels.db import database_sync_to_async

from simulator.tasks import run_simulation
from web.channels._base_consumer import Twin4DemAsyncConsumer


class SimulationAsyncConsumer(Twin4DemAsyncConsumer):
    def __init__(self):
        super().__init__(run_simulation)
        self._persistence = get_simulation_persistence()

    async def step_finished(self, event):
        await database_sync_to_async(self._persistence.persist_step)(event["payload"])
        await self._send_json(event["payload"])
        await self._send_json({"status": "task completed"})

    async def _on_task_started(self):
        simulation_id = int(
            self.scope.get("url_route", {}).get("kwargs", {}).get("simulation_id")
        )
        await self._send_json({"status": f"task {simulation_id} started"})
