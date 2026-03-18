from itertools import permutations
from random import choice, random

from api.services._random import random_weights, random_gauss, random_frequency
from api.services._base import SimulationBuilder
from common.models import (
    Cabinet,
    PartySettings,
    Minister,
    JudgeLink,
    Judge,
    Court,
    MemberOfParliament,
    Parliament,
    MinisterLink,
)


class RandomSimulationBuilder(SimulationBuilder):
    def _create_cabinet(self, simulation) -> Cabinet:
        n = self._user_settings.government_size
        k = self._user_settings.government_connectivity_degree
        cabinet_label = self._get_label(simulation, self._user_settings, "-cabinet")
        cabinet = Cabinet.objects.create(
            label=cabinet_label,
            government_probability_for=self._user_settings.government_probability_for,
            legislative_probability=self._user_settings.legislative_path_probability,
        )

        majority_parties = list(
            self._user_settings.parties.filter(
                position=PartySettings.PartyPosition.MAJORITY
            )
        )

        prime_minister = Minister.objects.create(
            label=f"{cabinet_label}-pm",
            party=choice(majority_parties),
            is_prime_minister=True,
            cabinet=cabinet,
            influence=1.0,
            weights=random_weights(self._weights_count),
            personal_opinion=int(
                round(random_gauss(cabinet.government_probability_for, 0.1))
            ),
            appointing_group_opinion=random_frequency(
                cabinet.government_probability_for
            ),
            supporting_group_opinion=1.0,
        )

        ministers = [
            Minister.objects.create(
                label=f"{cabinet_label}-{i:02}",
                party=choice(majority_parties),
                is_prime_minister=False,
                cabinet=cabinet,
                influence=random(),
                weights=random_weights(self._weights_count),
                personal_opinion=int(
                    round(random_gauss(cabinet.government_probability_for, 0.1))
                ),
                appointing_group_opinion=random_frequency(
                    cabinet.government_probability_for
                ),
                supporting_group_opinion=1.0,
            )
            for i in range(1, n)
        ]

        links = self._build_minister_network(k, prime_minister, ministers)
        MinisterLink.objects.bulk_create(links)

        return cabinet

    def _create_parliament(self, simulation) -> Parliament:
        parliament_label = self._get_label(
            simulation, self._user_settings, "-parliament"
        )
        parliament = Parliament.objects.create(
            label=parliament_label,
            majority_probability_for=self._user_settings.parliament_majority_probability_for,
            opposition_probability_for=self._user_settings.parliament_opposition_probability_for,
        )
        mp_objects = []
        for party in self._user_settings.parties.all():
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
                    round(random_gauss(prob_distribution_center, spread=0.1))
                )
                return MemberOfParliament(
                    label=label,
                    is_head=is_head,
                    weights=random_weights(self._weights_count),
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

    def _create_court(self, simulation) -> Court:
        court_label = self._get_label(simulation, self._user_settings, "-court")
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
                weights=random_weights(6),
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
