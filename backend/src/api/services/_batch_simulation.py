import json
from itertools import permutations
from pathlib import Path
from typing import Optional

from api.services._base import SimulationBuilder
from api.services._random import random_weights
from common.dto import AggrandisementBatch
from common.models import (
    UserSettings,
    Simulation,
    Court,
    Parliament,
    Cabinet,
    Minister,
    PartySettings,
    MinisterLink,
    MemberOfParliament,
    Judge,
    JudgeLink,
)


class AggrandisementBatchBuilder(SimulationBuilder):
    def __init__(self, settings: UserSettings):
        super().__init__(settings)
        self.__aggrandisement_batch: Optional[AggrandisementBatch] = None
        self.__party_map = None

    def load_aggrandisement_batch(
        self, input_data: dict | Path
    ) -> "AggrandisementBatchBuilder":
        if isinstance(input_data, Path):
            with open(input_data, "r") as fp:
                self.__aggrandisement_batch = AggrandisementBatch.model_validate(
                    json.load(fp)
                )
        else:
            self.__aggrandisement_batch = AggrandisementBatch.model_validate(input_data)
        return self

    @property
    def aggrandisement_batch(self) -> AggrandisementBatch:
        return self.__aggrandisement_batch

    @property
    def _party_map(self) -> dict:
        if self.__party_map is None:
            self.__party_map = {p.label: p.id for p in PartySettings.objects.all()}
        return self.__party_map

    def _create_cabinet(self, simulation: Simulation) -> Cabinet:
        cabinet_label = self._get_label(simulation, self._user_settings, "-cabinet")
        cabinet = Cabinet.objects.create(
            label=cabinet_label,
            government_probability_for=self._user_settings.government_probability_for,
            legislative_probability=self._user_settings.legislative_path_probability,
        )
        executive_settings = self.__aggrandisement_batch.settings.executive
        ministers = [
            Minister(
                label=x.label,
                party_id=self._party_map[x.party],
                is_prime_minister=(x.label == executive_settings.prime_minister),
                cabinet=cabinet,
                influence=(
                    1.0
                    if (x.label == executive_settings.prime_minister)
                    else x.influence
                ),
                weights=random_weights(self._weights_count),
                personal_opinion=float(x.personal_opinion),
                appointing_group_opinion=float(x.appointing_group),
                supporting_group_opinion=float(x.supporting_group),
            )
            for x in executive_settings.ministers
        ]

        Minister.objects.bulk_create(ministers)

        # ministers must not contain the prime minister for network building
        prime_minister_idx = next(
            iter(idx for idx, x in enumerate(ministers) if x.is_prime_minister)
        )
        prime_minister = ministers.pop(prime_minister_idx)

        k = self._user_settings.government_connectivity_degree
        minister_links = self._build_minister_network(k, prime_minister, ministers)
        MinisterLink.objects.bulk_create(minister_links)

        return cabinet

    def _create_parliament(self, simulation: Simulation) -> Parliament:
        parliament_label = self._get_label(
            simulation, self._user_settings, "-parliament"
        )
        parliament = Parliament.objects.create(
            label=parliament_label,
            majority_probability_for=self._user_settings.parliament_majority_probability_for,
            opposition_probability_for=self._user_settings.parliament_opposition_probability_for,
        )
        legislative_settings = self.__aggrandisement_batch.settings.legislative
        mp_objects = [
            MemberOfParliament(
                label=x.label,
                is_head=x.label in legislative_settings.party_leaders,
                weights=random_weights(self._weights_count),
                party_id=self._party_map[x.party],
                parliament=parliament,
                personal_opinion=x.personal_opinion,
                appointing_group_opinion=x.appointing_group,
                supporting_group_opinion=x.supporting_group,
            )
            for x in legislative_settings.mps
        ]
        MemberOfParliament.objects.bulk_create(mp_objects)
        return parliament

    def _create_court(self, simulation: Simulation) -> Court:
        court_label = self._get_label(simulation, self._user_settings, "-court")
        judiciary_settings = self.__aggrandisement_batch.settings.judiciary
        court = Court.objects.create(
            label=court_label,
            probability_for=self._user_settings.court_probability_for,
        )
        judges = [
            Judge(
                label=x.label,
                is_president=(x.label == judiciary_settings.president),
                influence=(
                    1.0 if x.label == judiciary_settings.president else x.influence
                ),
                weights=random_weights(self._weights_count),
                court=court,
                party_id=self._party_map[x.party],
                personal_opinion=x.personal_opinion,
                appointing_group_opinion=x.appointing_group,
                supporting_group_opinion=x.supporting_group,
            )
            for x in judiciary_settings.judges
        ]
        links = [
            JudgeLink(from_judge=j1, to_judge=j2) for j1, j2 in permutations(judges, 2)
        ]
        Judge.objects.bulk_create(judges)
        JudgeLink.objects.bulk_create(links)
        return court
