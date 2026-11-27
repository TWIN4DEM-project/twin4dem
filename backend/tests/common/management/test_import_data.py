import csv
import shutil
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from common.models import (
    Country,
    Institution,
    InstitutionKind,
    Party,
    PartyPosition,
    UserSettings,
)

pytestmark = pytest.mark.django_db

PASSWORD = "importer-password"
LOGIN = ("--username=importer", f"--password={PASSWORD}")
RED_FIRST_POSITION = "b0000000-0000-4000-8000-000000000001"


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    """The default hasher takes about a second for each password and login."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def importer(django_user_model):
    return django_user_model.objects.create_superuser(
        username="importer", password=PASSWORD
    )


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


def run_import(source: Path) -> str:
    """Import `source` as the importer."""
    return run(source, *LOGIN)


def fail_import(source: Path) -> None:
    """Import `source`, which must fail. The reason is in the log."""
    with pytest.raises(CommandError, match="Import failed, nothing was saved."):
        run_import(source)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def matches(row: dict[str, str], where: dict[str, str]) -> bool:
    return all(row[column] == value for column, value in where.items())


def edit_rows(path: Path, where: dict[str, str], **changes: str) -> None:
    """Change the cells of the rows of a CSV file that have the values of `where`."""
    rows = read_rows(path)
    assert any(matches(row, where) for row in rows), f"{path.name}: no row {where}"
    write_rows(
        path, [{**row, **changes} if matches(row, where) else row for row in rows]
    )


def add_row(path: Path, where: dict[str, str], **changes: str) -> None:
    """Add to a CSV file a copy of the row with the values of `where`, changed."""
    rows = read_rows(path)
    [row] = [row for row in rows if matches(row, where)]
    write_rows(path, [*rows, {**row, **changes}])


def reverse_rows(path: Path) -> None:
    write_rows(path, read_rows(path)[::-1])


def add_senate(folder: Path, size: str) -> None:
    """Add a second legislative institution, Senate, with a chamber from 2020."""
    senate_id = str(uuid4())
    add_row(
        folder / "institution.csv",
        {"name": "Parliament"},
        institution_id=senate_id,
        name="Senate",
    )
    add_row(
        folder / "chamber.csv",
        {"size": "100"},
        chamber_id=str(uuid4()),
        institution_id=senate_id,
        size=size,
    )


def default_settings(user) -> UserSettings:
    return UserSettings.objects.get(user=user, label="default")


def create_testland(user) -> Country:
    return Country.objects.create(user_settings=default_settings(user), name="Testland")


def institutions(user) -> set[tuple]:
    """(branch, kind name, label, size) of each institution saved for `user`."""
    return set(
        Institution.objects.filter(kind__country__user_settings__user=user).values_list(
            "kind__branch", "kind__institution_name", "label", "size"
        )
    )


def institution(user, branch: str) -> Institution:
    return Institution.objects.get(
        kind__country__user_settings__user=user, kind__branch=branch
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


# What is imported


def test_imports_the_country_into_the_default_settings(testland, importer):
    run_import(testland)

    countries = default_settings(importer).countries.all()
    assert [country.name for country in countries] == ["Testland"]


def test_imports_into_the_settings_given(testland, importer):
    settings = UserSettings.objects.create(user=importer, label="Netherlands")

    run(testland, *LOGIN, "--user-settings=Netherlands")

    assert [country.name for country in settings.countries.all()] == ["Testland"]
    assert not default_settings(importer).countries.exists()


def test_imports_each_institution_with_its_most_recent_record(testland, importer):
    # the last chamber has no end date, so it is still active; the last
    # cabinet ended in 2024, but no cabinet came after it
    run_import(testland)

    assert institutions(importer) == {
        ("executive", "Government", "Cabinet B", 15),
        ("legislative", "Parliament", "Parliament", 100),
        ("judiciary", "Constitutional Court", "Constitutional Court", 9),
    }


def test_imports_the_parties_not_dissolved_with_their_most_recent_position(
    testland, importer
):
    # Green never had a position, Grey was dissolved in 2019
    run_import(testland)

    assert parties(importer) == {"Red", "Blue", "Green"}
    assert positions(importer) == {
        ("Red", "majority", "Parliament"),
        ("Blue", "opposition", "Parliament"),
    }


def test_every_country_goes_into_the_same_settings(testland_copy, importer, caplog):
    add_row(
        testland_copy / "country.csv",
        {"name": "Testland"},
        country_id=str(uuid4()),
        name="Otherland",
    )

    run_import(testland_copy)

    names = default_settings(importer).countries.values_list("name", flat=True)
    assert set(names) == {"Testland", "Otherland"}
    otherland = Country.objects.get(user_settings__user=importer, name="Otherland")
    assert not otherland.institution_kinds.exists()
    assert not otherland.parties.exists()
    assert "Otherland: no executive institution" in caplog.text


# Which records are taken


def test_order_of_the_rows_does_not_matter(testland_copy, importer):
    reverse_rows(testland_copy / "cabinet.csv")
    reverse_rows(testland_copy / "party-position.csv")

    run_import(testland_copy)

    assert institution(importer, "executive").label == "Cabinet B"
    assert positions(importer) == {
        ("Red", "majority", "Parliament"),
        ("Blue", "opposition", "Parliament"),
    }


def test_institution_without_records_is_not_imported(testland_copy, importer, caplog):
    add_row(
        testland_copy / "institution.csv",
        {"name": "Parliament"},
        institution_id=str(uuid4()),
        name="Senate",
    )

    run_import(testland_copy)

    assert {name for _, name, *_ in institutions(importer)} == {
        "Government",
        "Parliament",
        "Constitutional Court",
    }
    assert "'Senate' has no records, not imported." in caplog.text


def test_every_chamber_is_imported_with_the_same_positions(testland_copy, importer):
    add_senate(testland_copy, size="50")

    run_import(testland_copy)

    assert ("legislative", "Senate", "Senate", 50) in institutions(importer)
    assert positions(importer) == {
        ("Red", "majority", "Parliament"),
        ("Blue", "opposition", "Parliament"),
        ("Red", "majority", "Senate"),
        ("Blue", "opposition", "Senate"),
    }


def test_more_parties_than_seats_in_a_chamber_is_a_warning(
    testland_copy, importer, caplog
):
    add_senate(testland_copy, size="3")

    run_import(testland_copy)

    assert "3 parties for 3 seats in 'Senate'" in caplog.text
    assert "seats in 'Parliament'" not in caplog.text


def test_position_that_has_ended_is_still_imported(testland_copy, importer):
    # Grey's only position ended in 2019
    edit_rows(
        testland_copy / "political-party.csv", {"name": "Grey"}, date_dissolved=""
    )

    run_import(testland_copy)

    assert ("Grey", "opposition", "Parliament") in positions(importer)


# Running it again


def test_second_run_adds_nothing(testland, importer):
    run_import(testland)
    counts = record_counts()

    run_import(testland)

    assert record_counts() == counts


def test_reports_how_many_records_it_created(testland, importer):
    first = run_import(testland)
    second = run_import(testland)

    assert "party: 3 created" in first
    assert "party-position: 2 created" in first
    assert "Nothing created." in second


def test_existing_records_are_kept_and_the_rest_added(testland, importer):
    country = create_testland(importer)
    Party.objects.create(country=country, label="Red")

    run_import(testland)

    assert default_settings(importer).countries.count() == 1
    assert sorted(country.parties.values_list("label", flat=True)) == [
        "Blue",
        "Green",
        "Red",
    ]
    assert positions(importer) == {
        ("Red", "majority", "Parliament"),
        ("Blue", "opposition", "Parliament"),
    }


def test_records_of_another_user_are_not_reused(testland, importer, django_user_model):
    other_testland = create_testland(django_user_model.objects.create_user("other"))
    Party.objects.create(country=other_testland, label="Red")

    run_import(testland)

    assert parties(importer) == {"Red", "Blue", "Green"}
    assert list(other_testland.parties.values_list("label", flat=True)) == ["Red"]


# Missing files


def test_missing_court_imports_the_rest_and_warns(testland_copy, importer, caplog):
    (testland_copy / "court.csv").unlink()

    run_import(testland_copy)

    assert {branch for branch, *_ in institutions(importer)} == {
        "executive",
        "legislative",
    }
    assert "court.csv: file is missing" in caplog.text
    assert "no judiciary institution" in caplog.text


@pytest.mark.parametrize(
    "file_name",
    [
        "cabinet.csv",
        "chamber.csv",
        "court.csv",
        "political-party.csv",
        "party-position.csv",
    ],
)
def test_missing_optional_file_is_a_warning(testland_copy, importer, caplog, file_name):
    (testland_copy / file_name).unlink()

    run_import(testland_copy)

    assert f"{file_name}: file is missing, nothing imported from it." in caplog.text


def test_without_a_chamber_parties_are_imported_without_positions(
    testland_copy, importer, caplog
):
    (testland_copy / "chamber.csv").unlink()

    run_import(testland_copy)

    assert parties(importer) == {"Red", "Blue", "Green"}
    assert positions(importer) == set()
    assert "no chamber, party positions not imported" in caplog.text


@pytest.mark.parametrize("file_name", ["country.csv", "institution.csv"])
def test_missing_required_file_is_an_error(testland_copy, importer, caplog, file_name):
    (testland_copy / file_name).unlink()

    fail_import(testland_copy)

    assert f"{file_name}: required file is missing." in caplog.text


# File format


def test_byte_order_mark_is_accepted(testland_copy, importer):
    path = testland_copy / "country.csv"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())

    run_import(testland_copy)

    assert default_settings(importer).countries.filter(name="Testland").exists()


def test_non_utf8_file_is_an_error(testland_copy, importer, caplog):
    path = testland_copy / "country.csv"
    path.write_bytes(
        path.read_bytes().replace(b"Testland", "Testländ".encode("latin-1"))
    )

    fail_import(testland_copy)

    assert "country.csv: not a UTF-8 text file." in caplog.text


# Invalid data


@pytest.mark.parametrize(
    "file_name,where,changes,problem",
    [
        (
            "cabinet.csv",
            {"name": "Cabinet B"},
            {"size": "abc"},
            "cabinet.csv line 3: size:",
        ),
        (
            "country.csv",
            {"name": "Testland"},
            {"name": ""},
            "country.csv line 2: name:",
        ),
        (
            "party-position.csv",
            {"party_position_id": RED_FIRST_POSITION},
            {"position": "coalition"},
            "party-position.csv line 2: position:",
        ),
    ],
    ids=["wrong type", "missing value", "unknown choice"],
)
def test_invalid_value_is_an_error_and_nothing_is_saved(
    testland_copy, importer, caplog, file_name, where, changes, problem
):
    edit_rows(testland_copy / file_name, where, **changes)
    counts = record_counts()

    fail_import(testland_copy)

    assert problem in caplog.text
    assert record_counts() == counts


def test_record_rejected_by_the_api_rolls_back_the_whole_import(
    testland_copy, importer, caplog
):
    # the contract accepts the name, the API's 50-character party label does
    # not; Blue comes after Red, so records were already saved when it fails
    edit_rows(testland_copy / "political-party.csv", {"name": "Blue"}, name="B" * 51)
    counts = record_counts()

    fail_import(testland_copy)

    assert f"party '{'B' * 51}' of Testland" in caplog.text
    assert "no more than 50 characters" in caplog.text
    assert record_counts() == counts


def test_party_named_twice_in_the_file_is_imported_once(testland_copy, importer):
    add_row(
        testland_copy / "political-party.csv",
        {"name": "Green"},
        political_party_id=str(uuid4()),
    )

    run_import(testland_copy)

    assert parties(importer) == {"Red", "Blue", "Green"}


def test_user_without_permissions_is_refused(testland, django_user_model, caplog):
    django_user_model.objects.create_user("viewer", password=PASSWORD)
    counts = record_counts()

    with pytest.raises(CommandError, match="Import failed, nothing was saved."):
        run(testland, "--username=viewer", f"--password={PASSWORD}")

    assert "You do not have permission to perform this action." in caplog.text
    assert record_counts() == counts


# Command arguments


@pytest.mark.parametrize(
    "username,password", [("nobody", PASSWORD), ("importer", "wrong")]
)
def test_wrong_username_or_password_is_an_error(
    testland, importer, caplog, username, password
):
    with pytest.raises(CommandError, match="Import failed, nothing was saved."):
        run(testland, f"--username={username}", f"--password={password}")

    assert "Invalid username or password." in caplog.text


def test_password_is_asked_when_not_given(testland, importer, monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt: PASSWORD)

    run(testland, "--username=importer")

    assert parties(importer) == {"Red", "Blue", "Green"}


def test_unknown_settings_is_an_error(testland, importer, caplog):
    with pytest.raises(CommandError, match="Import failed, nothing was saved."):
        run(testland, *LOGIN, "--user-settings=nowhere")

    assert "settings 'nowhere' not found." in caplog.text


@pytest.mark.parametrize("name", ["nowhere", "country.csv"])  # missing, a file
def test_source_must_be_an_existing_folder(testland, importer, name):
    with pytest.raises(CommandError, match="does not exist or is not a folder"):
        run(testland / name, "--username=importer")
