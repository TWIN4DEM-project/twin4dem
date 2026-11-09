from django.db.models import RestrictedError
from rest_framework import permissions, routers, status, viewsets
from rest_framework.exceptions import APIException

from api.serializers import PartySerializer
from common.models import Party


class PartyInUse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "party_in_use"
    default_detail = "The party has agents in simulations and cannot be deleted."


class PartyViewSet(viewsets.ModelViewSet):
    serializer_class = PartySerializer
    permission_classes = [
        permissions.IsAuthenticated,
        permissions.DjangoModelPermissions,
    ]
    http_method_names = ["get", "head", "post", "put", "delete"]

    def get_queryset(self):
        parties = Party.objects.order_by("id")
        if self.request.user.is_superuser:
            return parties
        return parties.filter(country__user_settings__user=self.request.user)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except RestrictedError as e:
            raise PartyInUse() from e


router = routers.SimpleRouter()
router.register("party", PartyViewSet, basename="party")
