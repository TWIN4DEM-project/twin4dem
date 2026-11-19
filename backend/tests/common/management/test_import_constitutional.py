import shutil
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from common.models import UserSettings

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


def run(source: Path, *args: str) -> list[str]:
    out = StringIO()
    call_command("import_constitutional", str(source), *args, stdout=out)
    return out.getvalue().splitlines()


def test_imports_and_reports_per_model(testland, importer):
    output = run(testland, "--username=importer", f"--as-of={AS_OF}")

    assert output == [
        f"Imported {testland} as of {AS_OF} for importer.",
        "User settings: 1 created, 0 skipped",
        "Countries: 1 created, 0 skipped",
        "Institution kinds: 3 created, 0 skipped",
        "Institutions: 3 created, 0 skipped",
        "Parties: 2 created, 0 skipped",
        "Party positions: 2 created, 0 skipped",
        "Warning: Testland: 2 of 4 parties skipped: no position on 2023-12-31, "
        "or not active on that date.",
    ]
    assert UserSettings.objects.filter(user=importer, label="Testland").exists()


def test_second_run_only_skips(testland, importer):
    run(testland, "--username=importer", f"--as-of={AS_OF}")

    output = run(testland, "--username=importer", f"--as-of={AS_OF}")

    assert "Parties: 0 created, 2 skipped" in output
    assert "Party positions: 0 created, 2 skipped" in output


def test_as_of_defaults_to_today(testland, importer):
    output = run(testland, "--username=importer")

    assert (
        output[0] == f"Imported {testland} as of {timezone.localdate()} for importer."
    )


def test_warnings_of_every_step_are_shown(testland_copy, importer):
    (testland_copy / "court.csv").unlink()

    output = run(testland_copy, "--username=importer", f"--as-of={AS_OF}")

    assert "Warning: court.csv: file is missing, nothing imported from it." in output
    assert (
        "Warning: Testland: no judiciary institution, imported without one." in output
    )


def test_unknown_user_is_an_error(testland):
    with pytest.raises(CommandError, match="User 'nobody' does not exist."):
        run(testland, "--username=nobody")


def test_invalid_as_of_is_an_error(testland, importer):
    with pytest.raises(CommandError, match="--as-of"):
        run(testland, "--username=importer", "--as-of=yesterday")


def test_missing_source_is_an_error(tmp_path, importer):
    with pytest.raises(CommandError, match="does not exist"):
        run(tmp_path / "nowhere", "--username=importer")


def test_invalid_data_is_an_error_and_nothing_is_saved(testland_copy, importer):
    cabinets = testland_copy / "cabinet.csv"
    cabinets.write_bytes(cabinets.read_bytes().replace(b",15,", b",abc,"))

    with pytest.raises(CommandError, match=r"cabinet\.csv line 3: size"):
        run(testland_copy, "--username=importer", f"--as-of={AS_OF}")
    assert not UserSettings.objects.filter(user=importer, label="Testland").exists()
