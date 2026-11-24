import csv
import shutil
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    InstitutionKind,
    Party,
    PartyPosition,
    UserSettings,
)

pytestmark = pytest.mark.django_db

AS_OF = "2025-06-01"
PASSWORD = "importer-password"
LOGIN = ("--username=importer", f"--password={PASSWORD}")
RED_FIRST_POSITION = "b0000000-0000-4000-8000-000000000001"
BLUE_CURRENT_POSITION = "b0000000-0000-4000-8000-000000000004"
GREY_POSITION = "b0000000-0000-4000-8000-000000000005"


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


def run_import(source: Path, as_of: str = AS_OF) -> str:
    """Import `source` as the importer, as of `as_of`."""
    return run(source, *LOGIN, f"--as-of={as_of}")


def fail_import(source: Path, as_of: str = AS_OF) -> None:
    """Import `source`, which must fail. The reason is in the log."""
    with pytest.raises(CommandError, match="Import failed, nothing was saved."):
        run_import(source, as_of)


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

    run(testland, *LOGIN, f"--as-of={AS_OF}", "--user-settings=Netherlands")

    assert [country.name for country in settings.countries.all()] == ["Testland"]
    assert not default_settings(importer).countries.exists()


def test_imports_the_latest_institutions_started_by_the_import_date(testland, importer):
    run_import(testland)

    assert institutions(importer) == {
        ("executive", "Government", "Cabinet B", 15),
        ("legislative", "Parliament", "Parliament", 100),
        ("judiciary", "Constitutional Court", "Constitutional Court", 9),
    }


def test_imports_the_parties_active_at_the_end_of_the_cabinet(
    testland, importer, caplog
):
    # Cabinet B ended on 2024-01-01: Red and Blue have a position on its last
    # day, Green never had one and Grey was dissolved in 2019
    run_import(testland)

    assert parties(importer) == {"Red", "Blue", "Green"}
    assert positions(importer) == {
        ("Red", "majority", "Parliament"),
        ("Blue", "opposition", "Parliament"),
    }
    assert "1 of 4 parties skipped: not active on 2023-12-31." in caplog.text


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


# Which institution records are taken


@pytest.mark.parametrize(
    "as_of,cabinet",
    [
        ("2018-06-01", "Cabinet A"),
        ("2019-12-31", "Cabinet A"),
        ("2020-01-01", "Cabinet B"),  # the end day of Cabinet A is excluded
        ("2025-06-01", "Cabinet B"),  # none valid: the most recent
    ],
)
def test_imports_the_cabinet_valid_on_the_date_else_the_most_recent(
    testland, importer, as_of, cabinet
):
    run_import(testland, as_of)

    assert institution(importer, "executive").label == cabinet


def test_chamber_and_court_follow_the_same_rule(testland, importer):
    run_import(testland, "2018-06-01")

    assert institution(importer, "legislative").size == 90
    assert institution(importer, "judiciary").size == 9


def test_institution_starting_after_the_date_is_not_imported(
    testland, importer, caplog
):
    run_import(testland, "2014-06-01")

    assert {branch for branch, *_ in institutions(importer)} == {"judiciary"}
    assert "'Government' has no records valid on or before 2014-06-01" in caplog.text
    assert "'Parliament' has no records valid on or before 2014-06-01" in caplog.text


def test_more_than_one_institution_per_branch_is_an_error(
    testland_copy, importer, caplog
):
    add_row(
        testland_copy / "institution.csv",
        {"name": "Parliament"},
        institution_id=str(uuid4()),
        name="Senate",
    )

    fail_import(testland_copy)

    assert (
        "Testland: 2 legislative institutions ('Parliament', 'Senate')" in caplog.text
    )


# Which parties are taken


def test_parties_are_taken_on_the_import_date_while_the_cabinet_is_valid(
    testland, importer
):
    run_import(testland, "2018-06-01")  # Cabinet A is valid until 2020

    assert positions(importer) == {
        ("Red", "opposition", "Parliament"),
        ("Blue", "majority", "Parliament"),
        ("Grey", "opposition", "Parliament"),
    }


def test_without_a_cabinet_parties_are_taken_on_the_import_date(
    testland_copy, importer
):
    # Blue's position now ends after Cabinet B, but before the import date
    edit_rows(
        testland_copy / "party-position.csv",
        {"party_position_id": BLUE_CURRENT_POSITION},
        valid_to="2025-01-01",
    )
    (testland_copy / "cabinet.csv").unlink()

    run_import(testland_copy)

    assert positions(importer) == {("Red", "majority", "Parliament")}


def test_party_without_a_position_on_the_date_is_imported_without_one(
    testland_copy, importer
):
    # Cabinet B ended on 2024-01-01, Blue's last position now ends in 2022
    edit_rows(
        testland_copy / "party-position.csv",
        {"party_position_id": BLUE_CURRENT_POSITION},
        valid_to="2022-01-01",
    )

    run_import(testland_copy)

    assert "Blue" in parties(importer)
    assert positions(importer) == {("Red", "majority", "Parliament")}


@pytest.mark.parametrize(
    "as_of,imported", [("2019-05-31", True), ("2019-06-01", False)]
)
def test_party_is_skipped_from_its_dissolution_day(
    testland_copy, importer, as_of, imported
):
    # Grey's position stays open, so only its dissolution on 2019-06-01 counts
    edit_rows(
        testland_copy / "party-position.csv",
        {"party_position_id": GREY_POSITION},
        valid_to="",
    )

    run_import(testland_copy, as_of)

    assert ("Grey" in parties(importer)) is imported


def test_party_is_skipped_before_it_was_founded(testland_copy, importer):
    edit_rows(
        testland_copy / "political-party.csv",
        {"name": "Red"},
        date_founded="2021-01-01",
    )

    run_import(testland_copy, "2020-06-01")

    assert "Red" not in parties(importer)


def test_explicit_independent_position_is_imported(testland_copy, importer):
    edit_rows(
        testland_copy / "party-position.csv",
        {"party_position_id": BLUE_CURRENT_POSITION},
        position="independent",
    )

    run_import(testland_copy)

    assert ("Blue", "independent", "Parliament") in positions(importer)


def test_position_without_start_counts_from_the_beginning(testland_copy, importer):
    edit_rows(
        testland_copy / "party-position.csv",
        {"party_position_id": GREY_POSITION},
        valid_from="",
    )
    edit_rows(testland_copy / "chamber.csv", {"size": "90"}, valid_from="2000-01-01")

    run_import(testland_copy, "2010-01-01")  # the other positions start in 2015

    assert positions(importer) == {("Grey", "opposition", "Parliament")}


def test_more_parties_than_seats_is_a_warning(testland_copy, importer, caplog):
    edit_rows(testland_copy / "chamber.csv", {"size": "100"}, size="3")

    run_import(testland_copy)

    assert "3 parties for 3 seats in 'Parliament'" in caplog.text


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


def test_run_on_another_date_keeps_what_exists_and_adds_the_rest(testland, importer):
    run_import(testland)  # Cabinet B, Red majority

    run_import(testland, "2018-06-01")  # Cabinet A, Red opposition, Grey

    assert institution(importer, "executive").label == "Cabinet B"
    assert positions(importer) == {
        ("Red", "majority", "Parliament"),
        ("Blue", "opposition", "Parliament"),
        ("Grey", "opposition", "Parliament"),
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


def test_quoted_values_may_contain_commas(testland_copy, importer):
    edit_rows(testland_copy / "country.csv", {"name": "Testland"}, name="Test, land")

    run_import(testland_copy)

    assert default_settings(importer).countries.filter(name="Test, land").exists()


def test_byte_order_mark_is_accepted(testland_copy, importer):
    path = testland_copy / "country.csv"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())

    run_import(testland_copy)

    assert default_settings(importer).countries.filter(name="Testland").exists()


def test_other_files_in_the_folder_are_ignored(testland_copy, importer, caplog):
    (testland_copy / "README.md").write_bytes(b"# notes")

    run_import(testland_copy)

    assert "README" not in caplog.text
    assert parties(importer) == {"Red", "Blue", "Green"}


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


def test_institution_name_taken_by_another_branch_is_an_error(
    testland, importer, caplog
):
    InstitutionKind.objects.create(
        country=create_testland(importer),
        institution_name="Parliament",
        branch=InstitutionBranch.EXECUTIVE,
    )
    counts = record_counts()

    fail_import(testland)

    assert "already exists" in caplog.text
    assert record_counts() == counts


# Command arguments


def test_as_of_defaults_to_today(testland, importer):
    assert str(timezone.localdate()) in run(testland, *LOGIN)


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

    run(testland, "--username=importer", f"--as-of={AS_OF}")

    assert parties(importer) == {"Red", "Blue", "Green"}


def test_unknown_settings_is_an_error(testland, importer, caplog):
    with pytest.raises(CommandError, match="Import failed, nothing was saved."):
        run(testland, *LOGIN, "--user-settings=nowhere")

    assert "settings 'nowhere' not found." in caplog.text


def test_invalid_as_of_is_an_error(testland, importer):
    with pytest.raises(CommandError, match="--as-of"):
        run(testland, "--username=importer", "--as-of=yesterday")


@pytest.mark.parametrize("name", ["nowhere", "country.csv"])  # missing, a file
def test_source_must_be_an_existing_folder(testland, importer, name):
    with pytest.raises(CommandError, match="does not exist or is not a folder"):
        run(testland / name, "--username=importer")
