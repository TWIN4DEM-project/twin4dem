from django.db.models import RestrictedError
from rest_framework import permissions, routers, serializers, status, viewsets
from rest_framework.exceptions import APIException

from api.serializers import InstitutionSerializer
from common.models import Institution, InstitutionBranch

from ._batch import BatchCreateMixin


class InstitutionInUse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "institution_in_use"
    default_detail = "The institution is used in simulations and cannot be deleted."


class InstitutionFilter(serializers.Serializer):
    kind = serializers.IntegerField(required=False)
    branch = serializers.ChoiceField(
        choices=InstitutionBranch.choices, required=False, source="kind__branch"
    )
    country = serializers.IntegerField(required=False, source="kind__country")


class InstitutionViewSet(BatchCreateMixin, viewsets.ModelViewSet):
    serializer_class = InstitutionSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        permissions.DjangoModelPermissions,
    ]
    http_method_names = ["get", "head", "post", "put", "delete"]

    def get_queryset(self):
        institutions = Institution.objects.order_by("id")
        if not self.request.user.is_superuser:
            institutions = institutions.filter(
                kind__country__user_settings__user=self.request.user
            )
        if self.action == "list":
            filters = InstitutionFilter(data=self.request.query_params)
            filters.is_valid(raise_exception=True)
            institutions = institutions.filter(**filters.validated_data)
        return institutions

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except RestrictedError as e:
            raise InstitutionInUse() from e


router = routers.SimpleRouter()
router.register("institution", InstitutionViewSet, basename="institution")
