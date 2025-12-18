from random import choice, random, sample, randint

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from rest_framework import mixins, viewsets, permissions, routers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from common.models import (
    Simulation,
    UserSettings,
    Cabinet,
    SimulationParams,
    Minister,
    PartySettings,
    MinisterLink,
)
from api.serializers import (
    SimulationSerializer,
    SimulationListSerializer,
    SimulationPatchSerializer,
)


class SimulationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch"]

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
            case _:
                return SimulationSerializer

    def partial_update(self, request, *args, **kwargs):
        super().partial_update(request, *args, **kwargs)
        sim_id = kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        return Response(
            {"detail": f"simulation {sim_id} updated"},
            status=status.HTTP_202_ACCEPTED,
        )

    @transaction.atomic
    def perform_create(self, serializer):
        try:
            user_settings = UserSettings.objects.get(user=self.request.user)
        except UserSettings.DoesNotExist:
            raise PermissionDenied("User settings not found")

        sim = serializer.save(user_settings=user_settings)
        cab = self._create_cabinet(sim, user_settings)
        ct = ContentType.objects.get_for_model(Cabinet)
        SimulationParams.objects.create(simulation=sim, type=ct, content_id=cab.id)

    @classmethod
    def _create_cabinet(cls, simulation, user_settings: UserSettings) -> Cabinet:
        sim_label = f"simulation-{simulation.id:06}"
        n = user_settings.government_size
        k = user_settings.government_connectivity_degree

        cabinet = Cabinet.objects.create(
            label=f"{user_settings.user.username}-{sim_label}",
            government_probability_for=user_settings.government_probability_for,
            legislative_probability=user_settings.legislative_path_probability,
        )

        majority_parties = list(
            user_settings.parties.filter(position=PartySettings.PartyPosition.MAJORITY)
        )

        # --- create ministers ---
        prime_minister = Minister.objects.create(
            label=f"{sim_label}-pm",
            party=choice(majority_parties),
            is_prime_minister=True,
            cabinet=cabinet,
            influence=1.0,
        )

        ministers = [
            Minister.objects.create(
                label=f"{sim_label}-{i:02}",
                party=choice(majority_parties),
                is_prime_minister=False,
                cabinet=cabinet,
                influence=random(),
            )
            for i in range(1, n)
        ]

        links = cls._build_minister_network(k, ministers, prime_minister)

        MinisterLink.objects.bulk_create(links)
        return cabinet

    @classmethod
    def _build_minister_network(
        cls, k: int, ministers: list[Minister], prime_minister: Minister
    ) -> list[MinisterLink]:
        all_nodes = ministers + [prime_minister]
        remaining_indegree = {m.id: k for m in ministers}
        links = []

        # PM influences everyone (PM is unconstrained)
        for m in ministers:
            links.append(MinisterLink(from_minister=prime_minister, to_minister=m))
            remaining_indegree[m.id] -= 1

        # Ministers influence others
        for minister in ministers:
            max_out = randint(1, k)

            candidates = [
                m
                for m in all_nodes
                if (
                    m != minister
                    and (m == prime_minister or remaining_indegree.get(m.id, 0) > 0)
                )
            ]

            if not candidates:
                # unlucky minister doesn't influence anybody
                continue

            degree = min(max_out, len(candidates))
            targets = sample(candidates, degree)

            for target in targets:
                links.append(MinisterLink(from_minister=minister, to_minister=target))
                if target != prime_minister:
                    remaining_indegree[target.id] -= 1

        return links


router = routers.SimpleRouter()
router.register("simulation", SimulationViewSet, basename="simulation")
