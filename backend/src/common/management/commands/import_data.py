from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import capfirst

from common.importing import (
    DataImportError,
    read_delivery,
    resolve_source,
    select,
    write,
)


class Command(BaseCommand):
    help = (
        "Import data (CSV files following the twin4dem data contracts) into "
        "the user settings of a user. Currently supports constitutional-level "
        "data. Records that already exist are skipped, so running it again "
        "only adds what is new."
    )

    def add_arguments(self, parser):
        parser.add_argument("source", help="Folder with the CSV files to import.")
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
        as_of = options["as_of"] or timezone.localdate()
        try:
            delivery = read_delivery(resolve_source(options["source"]))
            selections = select(delivery, as_of)
            result = write(selections, user)
        except DataImportError as e:
            raise CommandError(str(e)) from None

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {options['source']} as of {as_of} for {user}."
            )
        )
        for model in dict.fromkeys([*result.created, *result.skipped]):
            self.stdout.write(
                f"{capfirst(model._meta.verbose_name_plural)}: "
                f"{result.created[model]} created, {result.skipped[model]} skipped"
            )
        warnings = [
            *delivery.warnings,
            *(warning for s in selections for warning in s.warnings),
            *result.warnings,
        ]
        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"Warning: {warning}"))

    @staticmethod
    def _user(username: str):
        user_model = get_user_model()
        try:
            return user_model._default_manager.get_by_natural_key(username)
        except user_model.DoesNotExist:
            raise CommandError(f"User '{username}' does not exist.") from None
