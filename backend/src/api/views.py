from rest_framework.decorators import api_view, schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.schemas import AutoSchema

from common.models import UserSettings
from .serializers import UserSettingsSerializer


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
