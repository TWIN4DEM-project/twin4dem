import argparse
import getpass
import json
from datetime import datetime
from random import choice, random

from django.core.management.base import BaseCommand
from django.contrib.auth import authenticate

from common.models import UserSettings, PartySettings


AGENT_FILE_FIELDNAMES = [
    "label",
    "party",
    "personal_opinion",
    "appointing_group",
    "supporting_group",
]


class Command(BaseCommand):
    help = "Generate a sample aggrandisement batch based on user settings"

    @staticmethod
    def _positive_int(s: str) -> int:
        try:
            val = int(s)
            if val < 1:
                raise argparse.ArgumentTypeError(
                    f"{val} is less than or equal to zero."
                )
            return val
        except ValueError as e:
            raise argparse.ArgumentTypeError(f"invalid positive int {s}: {e}")

    @staticmethod
    def _probability(s: str) -> float:
        try:
            val = float(s)
            if val < 0 or 1 < val:
                raise argparse.ArgumentTypeError(f"{val} is not between [0, 1].")
            return val
        except ValueError as e:
            raise argparse.ArgumentTypeError(f"invalid float {s}: {e}")

    def add_arguments(self, parser):
        parser.add_argument(
            "--username", required=True, help="Username to authenticate"
        )
        parser.add_argument(
            "--password", required=False, help="Password for authentication"
        )
        parser.add_argument(
            "--start-date",
            required=True,
            help="Aggrandisement batch start date. ISO 8601 format (e.g., '2024-03-15T14:30:00')",
            type=datetime.fromisoformat,
        )
        parser.add_argument(
            "--end-date",
            required=True,
            help="Aggrandisement batch end date. ISO 8601 format (e.g., '2024-03-15T14:30:00')",
            type=datetime.fromisoformat,
        )
        parser.add_argument(
            "--aggrandisement-unit-count",
            required=False,
            default=1,
            help="The number of aggrandisement units contained in this batch.",
            type=self._positive_int,
        )
        parser.add_argument(
            "--belief-center",
            required=False,
            default=0.5,
            help="Value around which we center aggrandisement unit beliefs.",
            type=self._probability,
        )

    def _check_valid_timespan(self, options):
        start_date = options["start_date"]
        end_date = options["end_date"]
        if end_date <= start_date:
            self.stderr.write(
                self.style.ERROR("Error: --end-date must be after --start-date")
            )
            return None, None
        return start_date, end_date

    def _check_user(self, options):
        username = options["username"]
        password = options.get("password", None)
        if password is None:
            password = getpass.getpass(f"Enter {username}'s password:")
        user = authenticate(username=username, password=password)
        if not user:
            self.stderr.write(self.style.ERROR("Invalid credentials"))
            return None
        return user

    @staticmethod
    def random_freq(center: float) -> float:
        return 1 if random() >= center else 0

    @staticmethod
    def _generate_agent_beliefs(center: float) -> dict:
        return {
            "personalOpinion": Command.random_freq(center),
            "appointingGroup": Command.random_freq(center),
            "supportingGroup": Command.random_freq(center),
        }

    def _create_ministers(self, settings, majority_parties):
        return [
            {
                "label": f"minister-{idx}",
                "party": choice(majority_parties),
                "influence": random(),
                **self._generate_agent_beliefs(settings.government_probability_for),
            }
            for idx in range(1, settings.government_size + 1)
        ]

    def _create_members_of_parliament(self, settings, party_map, majority_parties):
        return [
            {
                "label": f"{party}-mp-{idx}",
                "party": party,
                **self._generate_agent_beliefs(
                    settings.parliament_majority_probability_for
                    if party in majority_parties
                    else settings.parliament_opposition_probability_for
                ),
            }
            for party, member_count in party_map.items()
            for idx in range(1, member_count + 1)
        ]

    def _create_judges(self, settings, party_map):
        parties = list(party_map)
        return [
            {
                "label": f"judge-{idx}",
                "party": choice(parties),
                "influence": random(),
                **self._generate_agent_beliefs(settings.court_probability_for),
            }
            for idx in range(1, settings.court_size + 1)
        ]

    def _create_aggrandisement_batch_settings(
        self,
        majority_parties: list[str],
        party_map: dict[str, int],
        settings: UserSettings,
    ):
        ministers = self._create_ministers(settings, majority_parties)
        prime_minister = choice(ministers)
        prime_minister["influence"] = 1.0

        mps = self._create_members_of_parliament(settings, party_map, majority_parties)
        party_leaders = [
            choice([mp["label"] for mp in mps if mp["party"] == p]) for p in party_map
        ]
        judges = self._create_judges(settings, party_map)
        court_president = choice(judges)
        court_president["influence"] = 1.0
        return {
            "executive": {
                "primeMinister": prime_minister["label"],
                "ministers": ministers,
            },
            "legislative": {
                "partyLeaders": party_leaders,
                "mps": mps,
            },
            "judiciary": {
                "president": court_president["label"],
                "judges": judges,
            },
        }

    def _create_aggrandisement_unit(self, step_no, batch_settings, center):
        minister_beliefs = [
            {
                "label": m["label"],
                **self._generate_agent_beliefs(center),
            }
            for m in batch_settings["executive"]["ministers"]
        ]
        mp_beliefs = [
            {
                "label": m["label"],
                **self._generate_agent_beliefs(center),
            }
            for m in batch_settings["legislative"]["mps"]
        ]
        judge_beliefs = [
            {
                "label": j["label"],
                **self._generate_agent_beliefs(center),
            }
            for j in batch_settings["judiciary"]["judges"]
        ]
        return {
            "step": step_no,
            "beliefs": {
                "ministers": minister_beliefs,
                "mps": mp_beliefs,
                "judges": judge_beliefs,
            },
        }

    def handle(self, *args, **options):
        start_date, end_date = self._check_valid_timespan(options)
        if start_date is None:
            return
        user = self._check_user(options)
        if user is None:
            return
        n = options["aggrandisement_unit_count"]
        center = options["belief_center"]
        settings = UserSettings.objects.get(user_id=user.id)
        party_map = {
            party.label: party.member_count for party in settings.parties.all()
        }
        majority_parties = [
            party.label
            for party in settings.parties.filter(
                position=PartySettings.PartyPosition.MAJORITY
            )
        ]
        batch_settings = self._create_aggrandisement_batch_settings(
            majority_parties, party_map, settings
        )
        aggrandisement_units = [
            self._create_aggrandisement_unit(step, batch_settings, center)
            for step in range(1, n + 1)
        ]
        output = json.dumps(
            {
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "settings": batch_settings,
                "aggrandisementUnits": aggrandisement_units,
            },
            indent=2,
        )

        # Now operate with authenticated user context
        self.stdout.write(output)
