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
    PartyPositionType,
    ChamberPayload,
    CourtPayload,
    Country,
    Party,
)

DEFAULT_PARTY_POSITION = PartyPositionType.INDEPENDENT

DEFAULT_PARLIAMENT_SIZE = 100
DEFAULT_COURT_SIZE = 5
DEFAULT_GOVT_CONNECTIVITY = 2
MAX_INDEPENDENT_POOL_SHARE = 8
MIN_SPLIT_WEIGHT = 1.0

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

    def _party_seats(
        self, country: Country
    ) -> list[tuple[Party, PartyPositionType, int]]:
        parties = list(country.parties.all())
        if not parties:
            return []

        positions = self._party_positions(parties)
        pool = self._parliament_size - len(parties)
        member_counts = self._allocate_member_seats(pool, parties, positions)
        return [
            (party, positions[party.id], member_counts[party.id]) for party in parties
        ]

    @staticmethod
    def _party_positions(parties: list[Party]) -> dict[int, PartyPositionType]:
        positions: dict[int, PartyPositionType] = {}
        for party in parties:
            latest = party.latest_position
            positions[party.id] = (
                PartyPositionType(latest.position)
                if latest is not None
                else DEFAULT_PARTY_POSITION
            )
        return positions

    def _allocate_member_seats(
        self, pool: int, parties: list[Party], positions: dict[int, PartyPositionType]
    ) -> dict[int, int]:
        blocs = {
            position_type: [
                party for party in parties if positions[party.id] == position_type
            ]
            for position_type in PartyPositionType
        }
        member_counts: dict[int, int] = {}
        for position_type, seats in self._bloc_member_seats(pool, blocs).items():
            member_counts.update(self._split_seats(seats, blocs[position_type]))
        return member_counts

    @staticmethod
    def _bloc_member_seats(
        pool: int, blocs: dict[PartyPositionType, list[Party]]
    ) -> dict[PartyPositionType, int]:
        majorities = blocs[PartyPositionType.MAJORITY]
        opposition = blocs[PartyPositionType.OPPOSITION]
        independents = blocs[PartyPositionType.INDEPENDENT]

        independent_seats = (
            randint(0, pool // MAX_INDEPENDENT_POOL_SHARE)
            if independents and pool > 0
            else 0
        )
        remaining = max(pool - independent_seats, 0)

        if majorities and opposition:
            head_gap = len(opposition) - len(majorities)
            opposition_seats = randint(
                0, min(max(0, (remaining - head_gap - 1) // 2), remaining)
            )
            majority_seats = remaining - opposition_seats
        elif majorities:
            majority_seats, opposition_seats = remaining, 0
        elif opposition:
            majority_seats, opposition_seats = 0, remaining
        else:
            independent_seats += remaining
            majority_seats, opposition_seats = 0, 0

        return {
            PartyPositionType.MAJORITY: majority_seats,
            PartyPositionType.OPPOSITION: opposition_seats,
            PartyPositionType.INDEPENDENT: independent_seats,
        }

    @staticmethod
    def _split_seats(total: int, bloc: list[Party]) -> dict[int, int]:
        if not bloc or total <= 0:
            return {party.id: 0 for party in bloc}

        weights = [MIN_SPLIT_WEIGHT + random() for _ in bloc]
        total_weight = sum(weights)
        exact = [weight * total / total_weight for weight in weights]
        seats = [int(value) for value in exact]
        leftover = max(total - sum(seats), 0)
        order = sorted(
            range(len(bloc)),
            key=lambda idx: exact[idx] - seats[idx],
            reverse=True,
        )
        for idx in order[:leftover]:
            seats[idx] += 1
        return {party.id: seat for party, seat in zip(bloc, seats)}

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
                opposition_probability_for=opposition_for,
            ),
            label=parliament_label,
            size=self._parliament_size,
        )
        mp_objects = []
        for party, position, member_count in self._party_seats(country):
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
                for idx in range(1, member_count + 1)
            )
        MemberOfParliament.objects.bulk_create(mp_objects)
        return parliament

    def _create_court(self) -> Institution:
        country = self._get_country()
        court_label = self._get_label(self._simulation, self._user_settings, "-court")
        probability_for = self._user_settings.court_probability_for
        court_institution_kind = InstitutionKind.objects.get_or_create(
            country=country,
            name=self._court_type,
            branch=InstitutionBranch.JUDICIARY,
        )
        court = Institution.objects.create(
            kind=court_institution_kind,
            label=court_label,
            size=self._court_size,
            payload=CourtPayload(probability_for=probability_for),
        )
        parties = list(country.parties.all())
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
