import getpass
import logging
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from twin4dem_data_contracts import models as contracts

from ._data_import._api import Api
from ._data_import._exceptions import DataImportError
from ._data_import._reader import read_records
from ._data_import._selection import select_institutions, select_parties
from ._data_import._writer import find_settings, write_country

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Import data (CSV files following the twin4dem data contracts) into "
        "the settings of a superuser, through the app's API. Currently supports "
        "constitutional-level data. Records that already exist are skipped, so "
        "running it again only adds what is new."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "source", type=Path, help="Folder with the CSV files to import."
        )
        parser.add_argument(
            "--username",
            required=True,
            help="Superuser to log in as, who receives the imported data.",
        )
        parser.add_argument(
            "--password", help="Password of the user (asked for if not given)."
        )
        parser.add_argument(
            "--user-settings",
            default="default",
            help="Label of the user's settings that receive the data "
            "(default: default).",
        )
        parser.add_argument(
            "--as-of",
            type=date.fromisoformat,
            help="Date the data is taken from, as YYYY-MM-DD (default: today).",
        )

    def handle(self, *args, **options):
        username = options["username"]
        source = options["source"]
        if not source.is_dir():
            raise CommandError(
                f"Import source '{source}' does not exist or is not a folder."
            )
        as_of = options["as_of"] or timezone.localdate()
        password = options["password"] or getpass.getpass(f"Password for {username}: ")
        try:
            api = Api(username, password)
            records = read_records(source)
            settings_id = find_settings(api, options["user_settings"])
            with transaction.atomic():
                for country in records[contracts.Country]:
                    institutions = select_institutions(records, country, as_of)
                    parties = select_parties(records, country, institutions, as_of)
                    write_country(api, settings_id, country, institutions, parties)
        except DataImportError as e:
            logger.error(e)
            raise CommandError("Import failed, nothing was saved.") from None

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {source} as of {as_of} into settings "
                f"'{options['user_settings']}' of {username}."
            )
        )
        for endpoint, count in api.created.items():
            self.stdout.write(f"{endpoint}: {count} created")
        if not api.created:
            self.stdout.write("Nothing created.")
