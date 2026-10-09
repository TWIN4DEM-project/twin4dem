from itertools import permutations
from random import choice, randint, random

from django.db.models import Q

from api.services._base import SimulationBuilder
from api.services._random import random_gauss, random_frequency
from api.services._weights import equal_weights
from common.models import (
    Minister,
    JudgeLink,
    Judge,
    MemberOfParliament,
    MinisterLink,
    Institution,
    CabinetPayload,
    UserSettings,
    InstitutionKind,
    InstitutionBranch,
    PartyPositionType, ChamberPayload, PartyPosition, )

DEFAULT_PARLIAMENT_SIZE = 100
DEFAULT_COURT_SIZE = 5
DEFAULT_GOVT_CONNECTIVITY = 2

CABINET_INSTITUTION_KIND = "cabinet"
COURT_INSTITUTION_KIND = "court"
PARLIAMENT_INSTITUTION_KIND = "parliament"


class RandomSimulationBuilder(SimulationBuilder):
    def __init__(
        self,
        settings: UserSettings,
        government_max_connectivity: int | None = None,
        cabinet_type: str = CABINET_INSTITUTION_KIND,
        chamber_type: str = PARLIAMENT_INSTITUTION_KIND,
        court_type: str = COURT_INSTITUTION_KIND,
    ) -> None:
        super().__init__(settings)
        self._k = int(government_max_connectivity or DEFAULT_GOVT_CONNECTIVITY)
        self._cabinet_size = randint(self._k + 1, self._k * 4 + 1)
        self._cabinet_type = cabinet_type
        self._parliament_size = DEFAULT_PARLIAMENT_SIZE
        self._chamber_type = chamber_type
        self._court_size = DEFAULT_COURT_SIZE
        self._court_type = court_type

    def _create_cabinet(self) -> Institution:
        cabinet_label = self._get_label(
            self._simulation, self._user_settings, "-cabinet"
        )
        country = self._get_country()

        probability_for = self._user_settings.government_probability_for
        cabinet_data = CabinetPayload(
            connectivity_degree=self._k, probability_for=probability_for
        )
        institution_kind = InstitutionKind.objects.get_or_create(
            country=country, branch=InstitutionBranch.EXECUTIVE, type=self._cabinet_type
        )
        result = Institution.objects.create(
            kind=institution_kind,
            label=cabinet_label,
            size=self._cabinet_size,
            payload=cabinet_data,
        )
        cabinet = self._link_institution_to_simulation(self._simulation, result)
        majority_parties = list(
            country.parties.filter(
                Q(positions__position__exact=PartyPositionType.MAJORITY)
            )
        )
        prime_minister = Minister.objects.create(
            label=f"{cabinet_label}-pm",
            party=choice(majority_parties),
            is_prime_minister=True,
            cabinet=cabinet,
            influence=1.0,
            weights=equal_weights(self._weights_count),
            personal_opinion=int(round(random_gauss(probability_for, 0.1))),
            appointing_group_opinion=random_frequency(probability_for),
            supporting_group_opinion=1.0,
        )

        ministers = [
            Minister.objects.create(
                label=f"{cabinet_label}-{i:02}",
                party=choice(majority_parties),
                is_prime_minister=False,
                cabinet=cabinet,
                influence=random(),
                weights=equal_weights(self._weights_count),
                personal_opinion=int(round(random_gauss(probability_for, 0.1))),
                appointing_group_opinion=random_frequency(probability_for),
                supporting_group_opinion=1.0,
            )
            for i in range(1, self._cabinet_size)
        ]

        links = self._build_minister_network(self._k, prime_minister, ministers)
        MinisterLink.objects.bulk_create(links)

        return result

    def _create_parliament(self) -> Institution:
        country = self._get_country()
        parliament_label = self._get_label(
            self._simulation, self._user_settings, "-parliament"
        )
        majority_for = self._user_settings.parliament_majority_probability_for
        opposition_for = self._user_settings.parliament_opposition_probability_for
        institution_kind = InstitutionKind.objects.get_or_create(
            country=country, branch=InstitutionBranch.EXECUTIVE, type=self._cabinet_type
        )
        parliament = Institution.objects.create(
            kind=institution_kind,
            payload=ChamberPayload(
                majority_probability_for=majority_for,
                opposition_probability_for=opposition_for
            ),
            label=parliament_label,
            size=self._parliament_size,
        )
        mp_objects = []
        remaining = self._parliament_size
        for party in country.parties.all():
            position = party.latest_position.position
            match position:
                case PartyPositionType.MAJORITY:
                    prob_distribution_center = parliament.majority_probability_for
                    o_sup1 = 1
                case PartyPositionType.OPPOSITION:
                    prob_distribution_center = parliament.opposition_probability_for
                    o_sup1 = 0
                case _:
                    prob_distribution_center = 0.5
                    o_sup1 = 0

            def _build_mp(label: str, is_head: bool) -> MemberOfParliament:
                personal_opinion = int(
                    round(random_gauss(prob_distribution_center, spread=0.1))
                )
                return MemberOfParliament(
                    label=label,
                    is_head=is_head,
                    weights=equal_weights(self._weights_count),
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

    def _create_court(self) -> Court:
        court_label = self._get_label(self._simulation, self._user_settings, "-court")
        court = Court.objects.create(
            label=court_label,
            probability_for=self._user_settings.court_probability_for,
        )
        parties = list(self._user_settings.parties.all())
        judges = [
            Judge(
                label=f"{court_label}-{idx:02}" if idx != 0 else f"{court_label}-P",
                is_president=(idx == 0),
                influence=random() if idx != 0 else 1.0,
                weights=equal_weights(6),
                court=court,
                party=choice(parties),
                personal_opinion=int(
                    round(random_gauss(court.probability_for, spread=0.1))
                ),
                appointing_group_opinion=0,
                supporting_group_opinion=0,
            )
            for idx in range(self._user_settings.court_size)
        ]
        links = [
            JudgeLink(from_judge=j1, to_judge=j2) for j1, j2 in permutations(judges, 2)
        ]
        Judge.objects.bulk_create(judges)
        JudgeLink.objects.bulk_create(links)
        return court

    def _init_aggrandisement_batch(self) -> None:
        pass
