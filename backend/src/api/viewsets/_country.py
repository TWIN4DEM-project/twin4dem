from django.db.models import RestrictedError
from rest_framework import permissions, routers, status, viewsets
from rest_framework.exceptions import APIException

from api.serializers import CountrySerializer
from common.models import Country


class CountryInUse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "country_in_use"
    default_detail = "The country has simulations and cannot be deleted."


class CountryViewSet(viewsets.ModelViewSet):
    serializer_class = CountrySerializer
    permission_classes = [
        permissions.IsAuthenticated,
        permissions.DjangoModelPermissions,
    ]
    http_method_names = ["get", "head", "post", "put", "delete"]

    def get_queryset(self):
        countries = Country.objects.order_by("id")
        if self.request.user.is_superuser:
            return countries
        return countries.filter(user_settings__user=self.request.user)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except RestrictedError as e:
            raise CountryInUse() from e


router = routers.SimpleRouter()
router.register("country", CountryViewSet, basename="country")
