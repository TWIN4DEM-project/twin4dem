from itertools import permutations
from random import choice, randint, random

from django.db.models import Q

from api.services._base import SimulationBuilder
from api.services._random import random_gauss, random_frequency
from api.services._weights import equal_weights
from common.party_seats import party_seats
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
    PartyPositionType,
    ChamberPayload,
    CourtPayload,
    SimulationInstitution,
)

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

    def _create_cabinet(self) -> SimulationInstitution:
        cabinet_label = self._get_label(
            self._simulation, self._user_settings, "-cabinet"
        )
        country = self._get_country()

        probability_for = self._user_settings.government_probability_for
        payload = CabinetPayload(
            connectivity_degree=self._k, probability_for=probability_for
        ).model_dump(mode="json")
        kind, _ = InstitutionKind.objects.get_or_create(
            country=country,
            branch=InstitutionBranch.EXECUTIVE,
            institution_name=self._cabinet_type,
        )
        cabinet_institution = Institution.objects.create(
            kind=kind,
            label=cabinet_label,
            size=self._cabinet_size,
            payload=payload,
        )
        cabinet = self._link_institution_to_simulation(
            self._simulation, cabinet_institution
        )
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

        return cabinet

    def _create_parliament(self) -> SimulationInstitution:
        country = self._get_country()
        parliament_label = self._get_label(
            self._simulation, self._user_settings, "-parliament"
        )
        majority_for = self._user_settings.parliament_majority_probability_for
        opposition_for = self._user_settings.parliament_opposition_probability_for
        kind, _ = InstitutionKind.objects.get_or_create(
            country=country,
            branch=InstitutionBranch.LEGISLATIVE,
            institution_name=self._chamber_type,
        )
        parliament_institution = Institution.objects.create(
            kind=kind,
            payload=ChamberPayload(
                majority_probability_for=majority_for,
                opposition_probability_for=opposition_for,
            ).model_dump(mode="json"),
            label=parliament_label,
            size=self._parliament_size,
        )
        parliament = self._link_institution_to_simulation(
            self._simulation, parliament_institution
        )
        mp_objects = []
        for party, position, member_count in party_seats(
            country, self._parliament_size
        ):
            match position:
                case PartyPositionType.MAJORITY:
                    prob_distribution_center = majority_for
                    o_sup1 = 1
                case PartyPositionType.OPPOSITION:
                    prob_distribution_center = opposition_for
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
                    chamber=parliament,
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
                for idx in range(1, member_count + 1)
            )
        MemberOfParliament.objects.bulk_create(mp_objects)
        return parliament

    def _create_court(self) -> SimulationInstitution:
        country = self._get_country()
        court_label = self._get_label(self._simulation, self._user_settings, "-court")
        probability_for = self._user_settings.court_probability_for
        kind, _ = InstitutionKind.objects.get_or_create(
            country=country,
            branch=InstitutionBranch.JUDICIARY,
            institution_name=self._court_type,
        )
        court_institution = Institution.objects.create(
            kind=kind,
            label=court_label,
            size=self._court_size,
            payload=CourtPayload(probability_for=probability_for).model_dump(
                mode="json"
            ),
        )
        court = self._link_institution_to_simulation(
            self._simulation, court_institution
        )
        parties = list(country.parties.all())
        judges = [
            Judge(
                label=f"{court_label}-{idx:02}" if idx != 0 else f"{court_label}-P",
                is_president=(idx == 0),
                influence=random() if idx != 0 else 1.0,
                weights=equal_weights(self._weights_count),
                court=court,
                party=choice(parties),
                personal_opinion=int(round(random_gauss(probability_for, spread=0.1))),
                appointing_group_opinion=0,
                supporting_group_opinion=0,
            )
            for idx in range(self._court_size)
        ]
        links = [
            JudgeLink(from_judge=j1, to_judge=j2) for j1, j2 in permutations(judges, 2)
        ]
        Judge.objects.bulk_create(judges)
        JudgeLink.objects.bulk_create(links)
        return court

    def _init_aggrandisement_batch(self) -> None:
        pass
