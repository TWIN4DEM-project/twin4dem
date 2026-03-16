from rest_framework.decorators import api_view, schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.schemas import AutoSchema

from common.models import UserSettings, Simulation
from .serializers import UserSettingsSerializer, SimulationLogSerializer


@api_view(["GET"])
@schema(AutoSchema)
def list_settings(req):
    """List all settings for the current user."""
    qs = UserSettings.objects.filter(user=req.user)
    serializer = UserSettingsSerializer(qs, many=True, context={"view": "list"})
    return Response(serializer.data)


@api_view(["GET"])
@schema(AutoSchema)
def get_settings(req, settings_id):
    """Retrieve individual settings for the current user by ID."""
    try:
        qs = UserSettings.objects.get(id=settings_id)
        serializer = UserSettingsSerializer(qs, many=False)
        return Response(serializer.data)
    except UserSettings.DoesNotExist:
        raise NotFound()


@api_view(["GET"])
@schema(AutoSchema)
def get_simulation_log(req, simulation_id):
    """Retrieve the results of the last N steps of a simulation.

    :param req: incoming HTTP request
    :param simulation_id: the ID of the simulation
    """
    max_steps = int(req.query_params.get("max_steps", 20))
    try:
        qs = (
            Simulation.objects.get(pk=simulation_id)
            .log.filter(simulation_id=simulation_id)
            .order_by("-step_no")[:max_steps]
        )
        serializer = SimulationLogSerializer(qs, many=True)
        return Response(serializer.data)
    except Simulation.DoesNotExist:
        raise NotFound(detail=f"simulation {simulation_id} not found")
