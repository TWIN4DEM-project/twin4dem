from caseswitcher import to_snake
from django.db.models import RestrictedError, QuerySet
from django.utils import timezone
from rest_framework import permissions, routers, serializers, status, viewsets
from rest_framework.exceptions import APIException

from api.serializers import (
    AllowedTimelineField,
    PartyListSerializer,
    PartyPositionSummaries,
    PartySerializer,
)
from common.models import Party, PartyPosition, PartyPositionType


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

    def get_serializer_class(self):
        if self.action == "list":
            return PartyListSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        parties = Party.objects.order_by("id").select_related("country")
        if self.request.user.is_superuser:
            parties = self._with_position_summaries(parties)
            return parties
        return self._with_position_summaries(
            parties.filter(country__user_settings__user=self.request.user)
        )

    def _with_position_summaries(self, parties: QuerySet) -> QuerySet:
        """Prefetch the latest/active positions, for the serializers to read."""
        if self.action != "list":
            return parties
        return PartyPositionSummaries.prefetch(parties, timeline=self.timeline)

    def _get_filter(self) -> PartyFilter | TimelineFilter:
        filter_cls = TimelineFilter
        if self.action == "list":
            filter_cls = PartyFilter
        filter_data = {to_snake(k): v for k, v in self.request.query_params.items()}
        return filter_cls(data=filter_data, context={"request": self.request})

    def filter_queryset(self, queryset):
        parties: QuerySet = super().filter_queryset(queryset)
        if self.action not in ("list", "retrieve"):
            return parties
        party_filter = self._get_filter()
        party_filter.is_valid(raise_exception=True)
        criteria = dict(party_filter.validated_data)
        self.timeline = criteria.pop("timeline", None)
        active_position = criteria.pop("active_position", None)
        if self.timeline is not None:
            parties = parties.filter(
                country__user_settings_id=self.timeline.user_settings_id
            )

        parties = parties.filter(**criteria)
        if active_position is not None:
            active = PartyPosition.objects.active_on(self.timeline, timezone.now())
            if self.timeline is not None:
                pass
            parties = parties.filter(
                positions__in=active.filter(position=active_position)
            ).distinct()
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
