from rest_framework.decorators import api_view, schema
from rest_framework.response import Response
from rest_framework.schemas import AutoSchema

_SAMPLE_USER_SETTINGS = {
    "id": 1,
    "userId": 1,
    "governmentSize": 5,
    "governmentConnectivityDegree": 2,
    "legislativePathProbability": 0.5,
    "parliamentSize": 100,
    "parties": [
        {"id": 1, "memberCount": 25, "position": "majority"},
        {"id": 2, "memberCount": 35, "position": "majority"},
        {"id": 3, "memberCount": 40, "position": "opposition"},
    ],
    "abstentionThreshold": 0.2,
    "courtSize": 5,
    "dataUpdateFrequency": 10,
}


@api_view(["GET"])
@schema(AutoSchema)
def list_settings(req):
    """List all settings for the current user."""
    data = [_SAMPLE_USER_SETTINGS]
    return Response(data)


@api_view(["GET"])
@schema(AutoSchema)
def get_settings(req, **_):
    """Retrieve individual settings for the current user by ID."""
    data = _SAMPLE_USER_SETTINGS
    return Response(data)
