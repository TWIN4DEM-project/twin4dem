import json
import zipfile
from http import HTTPStatus
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile, TemporaryUploadedFile
from django.core.files.uploadhandler import TemporaryFileUploadHandler
from django.db import transaction
from rest_framework import mixins, viewsets, permissions, routers, status
from rest_framework.exceptions import PermissionDenied, APIException
from rest_framework.response import Response

from api.services import RandomSimulationBuilder, AggrandisementBatchBuilder
from common.models import (
    Simulation,
    UserSettings,
)
from api.serializers import (
    SimulationSerializer,
    SimulationListSerializer,
    SimulationPatchSerializer,
    SimulationWithVoteStateSerializer,
)


BATCH_JSON_FILE_NAME = "batch.json"


def is_truthy(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


class UploadException(APIException):
    status_code = 400
    default_code = "invalid_upload"
    default_detail = "uploaded zip file was invalid"


class SimulationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    __WEIGHTS_COUNT = 6
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch"]

    def initialize_request(self, request, *args, **kwargs):
        result = super().initialize_request(request, *args, **kwargs)
        request.upload_handlers = [TemporaryFileUploadHandler()]
        return result

    def get_queryset(self):
        return Simulation.objects.filter(
            user_settings__user=self.request.user
        ).order_by("-created_at")

    def get_serializer_class(self):
        match self.action:
            case "list":
                return SimulationListSerializer
            case "partial_update":
                return SimulationPatchSerializer
            case "retrieve" if is_truthy(
                self.request.query_params.get("withHistoricVotes", "")
            ):
                return SimulationWithVoteStateSerializer
            case _:
                return SimulationSerializer

    def partial_update(self, request, *args, **kwargs):
        super().partial_update(request, *args, **kwargs)
        sim_id = kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        return Response(
            {"detail": f"simulation {sim_id} updated"},
            status=status.HTTP_202_ACCEPTED,
        )

    @staticmethod
    def _handle_zip_file(uploaded_file: UploadedFile):
        if not isinstance(uploaded_file, TemporaryUploadedFile):
            return Response(
                {"error": "File must be processed via TemporaryFileUploadHandler"},
                status=400,
            )
        temp_file_path = uploaded_file.temporary_file_path()
        try:
            with zipfile.ZipFile(temp_file_path, "r") as zip_ref:
                if BATCH_JSON_FILE_NAME not in zip_ref.namelist():
                    raise UploadException(
                        detail="Missing 'batch.json' in uploaded zip file"
                    )
                with zip_ref.open("batch.json") as json_file:
                    batch_data = json_file.read()
            return json.loads(batch_data)
        except zipfile.BadZipFile:
            raise UploadException()

    @transaction.atomic
    def perform_create(self, serializer):
        try:
            user_settings = UserSettings.objects.get(user=self.request.user)
        except UserSettings.DoesNotExist:
            raise PermissionDenied("User settings not found")

        if "file" in self.request.FILES:
            uploaded_file = self.request.FILES["file"]
            if uploaded_file.content_type not in [
                "application/zip",
                "application/x-zip-compressed",
            ]:
                raise APIException(
                    code=HTTPStatus.BAD_REQUEST, detail="Only ZIP files are supported"
                )

            obj = self._handle_zip_file(uploaded_file)
            builder = AggrandisementBatchBuilder(
                user_settings, Path(uploaded_file.name).stem
            )
            builder.load_aggrandisement_batch(obj).create(serializer)
        else:
            RandomSimulationBuilder(user_settings).create(serializer)


router = routers.SimpleRouter()
router.register("simulation", SimulationViewSet, basename="simulation")
