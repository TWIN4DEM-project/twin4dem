from caseswitcher import to_snake
from django.db.models import RestrictedError
from django.utils import timezone
from rest_framework import permissions, routers, serializers, status, viewsets
from rest_framework.exceptions import APIException

from api.serializers import AllowedTimelineField, PartySerializer, position_summaries
from common.models import Party, PartyPositionType


class PartyInUse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "party_in_use"
    default_detail = "The party has agents in simulations and cannot be deleted."


class CanAddNestedPositions(permissions.BasePermission):
    message = "Creating positions also requires the permission to add party positions."

    def has_permission(self, request, view):
        if request.method != "POST" or not isinstance(request.data, dict):
            return True
        if not request.data.get("positions"):
            return True
        return request.user.has_perm("common.add_partyposition")


class TimelineFilter(serializers.Serializer):
    timeline = AllowedTimelineField(required=False)


class PartyFilter(TimelineFilter):
    country = serializers.IntegerField(required=False)
    active_position = serializers.ChoiceField(
        choices=PartyPositionType.choices, required=False
    )


class PartyViewSet(viewsets.ModelViewSet):
    serializer_class = PartySerializer
    permission_classes = [
        permissions.IsAuthenticated,
        permissions.DjangoModelPermissions,
        CanAddNestedPositions,
    ]
    http_method_names = ["get", "head", "post", "put", "delete"]
    timeline = None

    def get_queryset(self):
        parties = Party.objects.order_by("id")
        if self.request.user.is_superuser:
            return parties
        return parties.filter(country__user_settings__user=self.request.user)

    def filter_queryset(self, queryset):
        parties = super().filter_queryset(queryset)
        if self.action not in ("list", "retrieve"):
            return parties
        filters = (PartyFilter if self.action == "list" else TimelineFilter)(
            data={to_snake(k): v for k, v in self.request.query_params.items()},
            context={"request": self.request},
        )
        filters.is_valid(raise_exception=True)
        criteria = dict(filters.validated_data)
        self.timeline = criteria.pop("timeline", None)
        if self.timeline is not None:
            parties = parties.filter(
                country__user_settings_id=self.timeline.user_settings_id
            )
        active_position = criteria.pop("active_position", None)
        parties = parties.filter(**criteria)
        if active_position is not None:
            summaries = position_summaries(list(parties), timezone.now(), self.timeline)
            parties = parties.filter(
                pk__in=[
                    pk
                    for pk, summary in summaries.items()
                    if summary.active is not None
                    and summary.active.position == active_position
                ]
            )
        return parties

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "timeline": self.timeline}

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except RestrictedError as e:
            raise PartyInUse() from e


router = routers.SimpleRouter()
router.register("party", PartyViewSet, basename="party")
