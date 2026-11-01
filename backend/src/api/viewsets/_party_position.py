from rest_framework import permissions, routers, serializers, viewsets

from api.serializers import PartyPositionSerializer
from common.models import PartyPosition


class PartyPositionFilter(serializers.Serializer):
    party = serializers.IntegerField(required=False)
    chamber = serializers.IntegerField(required=False)


class PartyPositionViewSet(viewsets.ModelViewSet):
    serializer_class = PartyPositionSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        permissions.DjangoModelPermissions,
    ]
    http_method_names = ["get", "head", "post", "put", "delete"]

    def get_queryset(self):
        positions = PartyPosition.objects.order_by("id")
        if not self.request.user.is_superuser:
            positions = positions.filter(
                party__country__user_settings__user=self.request.user
            )
        if self.action == "list":
            filters = PartyPositionFilter(data=self.request.query_params)
            filters.is_valid(raise_exception=True)
            positions = positions.filter(**filters.validated_data)
        return positions

    def get_serializer(self, *args, **kwargs):
        if self.action == "create" and isinstance(kwargs.get("data"), list):
            kwargs.update(many=True, allow_empty=False)
        return super().get_serializer(*args, **kwargs)


router = routers.SimpleRouter()
router.register("party-position", PartyPositionViewSet, basename="party-position")
