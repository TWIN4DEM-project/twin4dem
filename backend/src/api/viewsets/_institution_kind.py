from django.db.models import RestrictedError
from rest_framework import permissions, routers, serializers, status, viewsets
from rest_framework.exceptions import APIException

from api.serializers import InstitutionKindSerializer
from common.models import InstitutionBranch, InstitutionKind


class InstitutionKindInUse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "institution_kind_in_use"
    default_detail = (
        "The institution kind has institutions used in simulations and cannot be "
        "deleted."
    )


class CanAddNestedInstitutions(permissions.BasePermission):
    """
    Creating institutions together with their kind also requires the permission
    to add institutions.
    """

    message = "Creating institutions also requires the permission to add institutions."

    def has_permission(self, request, view):
        if request.method != "POST" or not isinstance(request.data, dict):
            return True
        if not request.data.get("institutions"):
            return True
        return request.user.has_perm("common.add_institution")


class InstitutionKindFilter(serializers.Serializer):
    country = serializers.IntegerField(required=False)
    branch = serializers.ChoiceField(choices=InstitutionBranch.choices, required=False)


class InstitutionKindViewSet(viewsets.ModelViewSet):
    serializer_class = InstitutionKindSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        permissions.DjangoModelPermissions,
        CanAddNestedInstitutions,
    ]
    http_method_names = ["get", "head", "post", "put", "delete"]

    def get_queryset(self):
        kinds = InstitutionKind.objects.prefetch_related("institutions").order_by("id")
        if not self.request.user.is_superuser:
            kinds = kinds.filter(country__user_settings__user=self.request.user)
        if self.action == "list":
            filters = InstitutionKindFilter(data=self.request.query_params)
            filters.is_valid(raise_exception=True)
            kinds = kinds.filter(**filters.validated_data)
        return kinds

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except RestrictedError as e:
            raise InstitutionKindInUse() from e


router = routers.SimpleRouter()
router.register("institution-kind", InstitutionKindViewSet, basename="institution-kind")
