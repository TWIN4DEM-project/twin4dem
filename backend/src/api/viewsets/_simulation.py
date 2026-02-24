from itertools import permutations
from random import choice, random, sample, randint, expovariate, gauss

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
    Parliament,
    MemberOfParliament,
    Court,
    Judge,
    JudgeLink,
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
    __WEIGHTS_COUNT = 6
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

    @staticmethod
    def _random_weights(n: int = 6) -> list[float]:
        x = [expovariate(1.0) for _ in range(n)]
        s = sum(x)
        return [x_i / s for x_i in x]

    @staticmethod
    def _random_gauss(
        center: float, spread: float = 1.0, lo: float = 0.0, hi: float = 1.0
    ) -> float:
        while not (lo <= (x := gauss(center, spread)) <= hi):
            continue
        return x

    @staticmethod
    def _random_frequency(center: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return hi if random() < center else lo

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

        parliament = self._create_parliament(sim, user_settings)
        ct = ContentType.objects.get_for_model(Parliament)
        SimulationParams.objects.create(
            simulation=sim, type=ct, content_id=parliament.id
        )

        court = self._create_court(sim, user_settings)
        ct = ContentType.objects.get_for_model(Court)
        SimulationParams.objects.create(simulation=sim, type=ct, content_id=court.id)

    @classmethod
    def _get_label(
        cls, simulation, user_settings: UserSettings, suffix: str = ""
    ) -> str:
        return f"{user_settings.user.username}-simulation-{simulation.id:06}{suffix}"

    @classmethod
    def _create_cabinet(cls, simulation, user_settings: UserSettings) -> Cabinet:
        n = user_settings.government_size
        k = user_settings.government_connectivity_degree
        cabinet_label = cls._get_label(simulation, user_settings, "-cabinet")
        cabinet = Cabinet.objects.create(
            label=cabinet_label,
            government_probability_for=user_settings.government_probability_for,
            legislative_probability=user_settings.legislative_path_probability,
        )

        majority_parties = list(
            user_settings.parties.filter(position=PartySettings.PartyPosition.MAJORITY)
        )

        # --- create ministers ---
        prime_minister = Minister.objects.create(
            label=f"{cabinet_label}-pm",
            party=choice(majority_parties),
            is_prime_minister=True,
            cabinet=cabinet,
            influence=1.0,
            weights=cls._random_weights(cls.__WEIGHTS_COUNT),
            personal_opinion=int(
                round(cls._random_gauss(cabinet.government_probability_for, 0.1))
            ),
            appointing_group_opinion=cls._random_frequency(cabinet.government_probability_for),
            supporting_group_opinion=1.0,
        )

        ministers = [
            Minister.objects.create(
                label=f"{cabinet_label}-{i:02}",
                party=choice(majority_parties),
                is_prime_minister=False,
                cabinet=cabinet,
                influence=random(),
                weights=cls._random_weights(cls.__WEIGHTS_COUNT),
                personal_opinion=int(
                    round(cls._random_gauss(cabinet.government_probability_for, 0.1))
                ),
                appointing_group_opinion=cls._random_frequency(cabinet.government_probability_for),
                supporting_group_opinion=1.0,
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

    @classmethod
    def _create_parliament(cls, simulation, user_settings: UserSettings) -> Parliament:
        parliament_label = cls._get_label(simulation, user_settings, "-parliament")
        parliament = Parliament.objects.create(
            label=parliament_label,
            majority_probability_for=user_settings.parliament_majority_probability_for,
            opposition_probability_for=user_settings.parliament_opposition_probability_for,
        )
        mp_objects = []
        for party in user_settings.parties.all():
            if party.position == PartySettings.PartyPosition.MAJORITY:
                prob_distribution_center = parliament.majority_probability_for
                o_sup1 = 1
            elif party.position == PartySettings.PartyPosition.OPPOSITION:
                prob_distribution_center = parliament.opposition_probability_for
                o_sup1 = 0
            else:
                prob_distribution_center = 0.5
                o_sup1 = 0

            def _build_mp(label: str, is_head: bool) -> MemberOfParliament:
                personal_opinion = int(
                    round(cls._random_gauss(prob_distribution_center, spread=0.1))
                )
                return MemberOfParliament(
                    label=label,
                    is_head=is_head,
                    weights=cls._random_weights(cls.__WEIGHTS_COUNT),
                    party=party,
                    parliament=parliament,
                    personal_opinion=personal_opinion,
                    appointing_group_opinion=o_sup1,
                    supporting_group_opinion=0,
                )

            mp_objects.append(
                _build_mp(
                    label=f"{parliament_label}-{party.label}-head",
                    is_head=True,
                )
            )
            mp_objects.extend(
                _build_mp(
                    label=f"{parliament_label}-{party.label}-member-{idx:03}",
                    is_head=False,
                )
                for idx in range(1, party.member_count)
            )
        MemberOfParliament.objects.bulk_create(mp_objects)
        return parliament


    @classmethod
    def _create_court(cls, simulation, user_settings: UserSettings) -> Court:
        court_label = cls._get_label(simulation, user_settings, "-court")
        court = Court.objects.create(
            label=court_label,
            probability_for=user_settings.court_probability_for,
        )
        parties = list(user_settings.parties.all())
        judges = [
            Judge(
                label=f"{court_label}-{idx:02}" if idx != 0 else f"{court_label}-P",
                is_president=(idx == 0),
                influence=random() if idx != 0 else 1.0,
                weights=cls._random_weights(6),
                court=court,
                party=choice(parties),
                personal_opinion=int(
                    round(cls._random_gauss(court.probability_for, spread=0.1))
                ),
                appointing_group_opinion=0,
                supporting_group_opinion=0,
            )
            for idx in range(user_settings.court_size)
        ]
        links = [
            JudgeLink(from_judge=j1, to_judge=j2) for j1, j2 in permutations(judges, 2)
        ]
        Judge.objects.bulk_create(judges)
        JudgeLink.objects.bulk_create(links)
        return court


router = routers.SimpleRouter()
router.register("simulation", SimulationViewSet, basename="simulation")
