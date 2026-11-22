from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import capfirst
from twin4dem_data_contracts.models import Country

from ._data_import._exceptions import DataImportError
from ._data_import._reader import read_records
from ._data_import._selection import select_institutions, select_parties
from ._data_import._writer import WriteResult, write_country


class Command(BaseCommand):
    help = (
        "Import data (CSV files following the twin4dem data contracts) into "
        "the user settings of a user. Currently supports constitutional-level "
        "data. Records that already exist are skipped, so running it again "
        "only adds what is new."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "source", type=Path, help="Folder with the CSV files to import."
        )
        parser.add_argument(
            "--username", required=True, help="User who receives the imported data."
        )
        parser.add_argument(
            "--as-of",
            type=date.fromisoformat,
            help="Date the data is taken from, as YYYY-MM-DD (default: today).",
        )

    def handle(self, *args, **options):
        user = self._user(options["username"])
        source = options["source"]
        if not source.is_dir():
            raise CommandError(
                f"Import source '{source}' does not exist or is not a folder."
            )
        as_of = options["as_of"] or timezone.localdate()
        warnings: list[str] = []
        result = WriteResult()
        try:
            records = read_records(source, warnings)
            with transaction.atomic():
                for country in records[Country]:
                    institutions = select_institutions(
                        records, country, as_of, warnings
                    )
                    parties = select_parties(
                        records, country, institutions, as_of, warnings
                    )
                    write_country(
                        user, country, institutions, parties, result, warnings
                    )
        except DataImportError as e:
            raise CommandError(str(e)) from None

        self.stdout.write(
            self.style.SUCCESS(f"Imported {source} as of {as_of} for {user}.")
        )
        for model in dict.fromkeys([*result.created, *result.skipped]):
            self.stdout.write(
                f"{capfirst(model._meta.verbose_name_plural)}: "
                f"{result.created[model]} created, {result.skipped[model]} skipped"
            )
        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"Warning: {warning}"))

    @staticmethod
    def _user(username: str):
        user_model = get_user_model()
        try:
            return user_model._default_manager.get_by_natural_key(username)
        except user_model.DoesNotExist:
            raise CommandError(f"User '{username}' does not exist.") from None
