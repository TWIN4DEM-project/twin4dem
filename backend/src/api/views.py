from datetime import datetime, timezone
from http import HTTPStatus

from rest_framework.decorators import api_view, schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.schemas import AutoSchema

from common.models import UserSettings
from .serializers import UserSettingsSerializer


_SAMPLE_USER_SETTINGS = {
    "id": 1,
    "userId": 1,
    "label": "default",
    "governmentSize": 15,
    "governmentConnectivityDegree": 3,
    "legislativePathProbability": 0.5,
    "parliamentSize": 100,
    "parties": [
        {"id": 1, "label": "Party A", "memberCount": 25, "position": "majority"},
        {"id": 2, "label": "Party B", "memberCount": 35, "position": "majority"},
        {"id": 3, "label": "Party C", "memberCount": 40, "position": "opposition"},
    ],
    "abstentionThreshold": 0.2,
    "courtSize": 5,
    "dataUpdateFrequency": 10,
}

_SAMPLE_SIMULATION = {
    "id": 1,
    "step": 0,
    "status": "new",
    "createdAt": datetime(2025, 12, 15, 21, 41, 0, 123, tzinfo=timezone.utc),
    "updatedAt": datetime(2025, 12, 15, 21, 41, 0, 124, tzinfo=timezone.utc),
    "globalParameters": _SAMPLE_USER_SETTINGS,
}


@api_view(["GET"])
@schema(AutoSchema)
def list_settings(req):
    """List all settings for the current user."""
    qs = UserSettings.objects.all()
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


@api_view(["GET", "POST"])
@schema(AutoSchema)
def create_or_list_simulations(req):
    """List all settings for the current user."""
    match req.method:
        case "GET":
            return Response(data=[_SAMPLE_SIMULATION])
        case "POST":
            return Response(status=HTTPStatus.CREATED, data=_SAMPLE_SIMULATION)
        case _:
            return Response(
                data={"reason": "unsupported method"},
                status=HTTPStatus.METHOD_NOT_ALLOWED,
            )


@api_view(["PATCH"])
@schema(AutoSchema)
def patch_simulation(req, simulation_id: int):
    """List all settings for the current user."""
    return Response(
        status=HTTPStatus.ACCEPTED,
        data={"detail": f"simulation {simulation_id} updated"},
    )
