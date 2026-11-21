import shutil
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from common.models import (
    Country,
    Institution,
    InstitutionKind,
    Party,
    PartyPosition,
    UserSettings,
)

pytestmark = pytest.mark.django_db

AS_OF = "2025-06-01"


@pytest.fixture
def importer(django_user_model):
    return django_user_model.objects.create_user(username="importer")


@pytest.fixture
def testland(data_dir) -> Path:
    return data_dir / "constitutional" / "testland"


@pytest.fixture
def testland_copy(testland, tmp_path) -> Path:
    """A copy of Testland that a test can edit."""
    return shutil.copytree(testland, tmp_path / "testland")


def run(source: Path, *args: str) -> str:
    out = StringIO()
    call_command("import_data", str(source), *args, stdout=out)
    return out.getvalue()


def institutions(user) -> set[tuple]:
    """(branch, kind name, label, size) of each institution saved for `user`."""
    return set(
        Institution.objects.filter(kind__country__user_settings__user=user).values_list(
            "kind__branch", "kind__institution_name", "label", "size"
        )
    )


def parties(user) -> set[str]:
    return set(
        Party.objects.filter(country__user_settings__user=user).values_list(
            "label", flat=True
        )
    )


def positions(user) -> set[tuple]:
    """(party, position, chamber) of each party position saved for `user`."""
    return set(
        PartyPosition.objects.filter(
            party__country__user_settings__user=user
        ).values_list("party__label", "position", "chamber__label")
    )


def record_counts() -> list[int]:
    """How many records there are of each model that the import saves."""
    imported = (
        UserSettings,
        Country,
        InstitutionKind,
        Institution,
        Party,
        PartyPosition,
    )
    return [model.objects.count() for model in imported]


def test_imports_the_country_into_settings_named_after_it(testland, importer):
    run(testland, "--username=importer", f"--as-of={AS_OF}")

    settings = UserSettings.objects.get(user=importer, label="Testland")
    assert [country.name for country in settings.countries.all()] == ["Testland"]


def test_imports_the_latest_institutions_started_by_the_import_date(testland, importer):
    run(testland, "--username=importer", f"--as-of={AS_OF}")

    assert institutions(importer) == {
        ("executive", "Government", "Cabinet B", 15),
        ("legislative", "Parliament", "Parliament", 100),
        ("judiciary", "Constitutional Court", "Constitutional Court", 9),
    }


def test_imports_the_parties_with_a_position_at_the_end_of_the_cabinet(
    testland, importer
):
    # Cabinet B ended on 2024-01-01: Red and Blue have a position on its last
    # day, Green never had one and Grey was dissolved in 2019
    output = run(testland, "--username=importer", f"--as-of={AS_OF}")

    assert parties(importer) == {"Red", "Blue"}
    assert positions(importer) == {
        ("Red", "majority", "Parliament"),
        ("Blue", "opposition", "Parliament"),
    }
    assert "2 of 4 parties skipped" in output


def test_second_run_adds_nothing(testland, importer):
    run(testland, "--username=importer", f"--as-of={AS_OF}")
    counts = record_counts()

    run(testland, "--username=importer", f"--as-of={AS_OF}")

    assert record_counts() == counts


def test_as_of_defaults_to_today(testland, importer):
    assert str(timezone.localdate()) in run(testland, "--username=importer")


def test_missing_court_imports_the_rest_and_warns(testland_copy, importer):
    (testland_copy / "court.csv").unlink()

    output = run(testland_copy, "--username=importer", f"--as-of={AS_OF}")

    assert {branch for branch, *_ in institutions(importer)} == {
        "executive",
        "legislative",
    }
    assert "court.csv: file is missing" in output
    assert "no judiciary institution" in output


def test_unknown_user_is_an_error(testland):
    with pytest.raises(CommandError, match="User 'nobody' does not exist."):
        run(testland, "--username=nobody")


def test_invalid_as_of_is_an_error(testland, importer):
    with pytest.raises(CommandError, match="--as-of"):
        run(testland, "--username=importer", "--as-of=yesterday")


@pytest.mark.parametrize("name", ["nowhere", "country.csv"])  # missing, a file
def test_source_must_be_an_existing_folder(testland, importer, name):
    with pytest.raises(CommandError, match="does not exist or is not a folder"):
        run(testland / name, "--username=importer")


def test_invalid_data_is_an_error_and_nothing_is_saved(testland_copy, importer):
    cabinets = testland_copy / "cabinet.csv"
    cabinets.write_bytes(cabinets.read_bytes().replace(b",15,", b",abc,"))
    counts = record_counts()

    with pytest.raises(CommandError, match=r"cabinet\.csv line 3: size"):
        run(testland_copy, "--username=importer", f"--as-of={AS_OF}")
    assert record_counts() == counts


def test_record_rejected_by_a_model_rolls_back_the_whole_import(
    testland_copy, importer
):
    # the contract accepts the name, the 50-character Party.label does not;
    # Blue comes after Red, so records were already saved when it fails
    parties_csv = testland_copy / "political-party.csv"
    parties_csv.write_bytes(
        parties_csv.read_bytes().replace(b",Blue,", b"," + b"B" * 51 + b",")
    )
    counts = record_counts()

    with pytest.raises(CommandError, match="at most 50 characters"):
        run(testland_copy, "--username=importer", f"--as-of={AS_OF}")
    assert record_counts() == counts
