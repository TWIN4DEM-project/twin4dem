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
RED_FIRST_POSITION = "b0000000-0000-4000-8000-000000000001"
BLUE_CURRENT_POSITION = "b0000000-0000-4000-8000-000000000004"
GREY_POSITION = "b0000000-0000-4000-8000-000000000005"
UNKNOWN_PARTY = "a0000000-0000-4000-8000-000000000009"


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


def run_import(source: Path, as_of: str = AS_OF) -> str:
    """Import `source` for the importer, as of `as_of`."""
    return run(source, "--username=importer", f"--as-of={as_of}")


def import_error(source: Path, as_of: str = AS_OF) -> str:
    """The message of the error that stops the import of `source`."""
    with pytest.raises(CommandError) as error:
        run_import(source, as_of)
    return str(error.value)


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


def create_testland(user) -> Country:
    settings = UserSettings.objects.create(user=user, label="Testland")
    return Country.objects.create(user_settings=settings, name="Testland")


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


def test_imports_the_country_into_settings_named_after_it(testland, importer):
    run_import(testland)

    settings = UserSettings.objects.get(user=importer, label="Testland")
    assert [country.name for country in settings.countries.all()] == ["Testland"]


def test_imports_the_latest_institutions_started_by_the_import_date(testland, importer):
    run_import(testland)

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
    output = run_import(testland)

    assert parties(importer) == {"Red", "Blue"}
    assert positions(importer) == {
        ("Red", "majority", "Parliament"),
        ("Blue", "opposition", "Parliament"),
    }
    assert "2 of 4 parties skipped" in output


def test_each_country_is_imported_into_its_own_settings(testland_copy, importer):
    add_row(
        testland_copy / "country.csv",
        {"name": "Testland"},
        country_id=str(uuid4()),
        name="Otherland",
    )

    output = run_import(testland_copy)

    labels = UserSettings.objects.filter(user=importer).values_list("label", flat=True)
    assert set(labels) == {"default", "Testland", "Otherland"}
    otherland = Country.objects.get(user_settings__user=importer, name="Otherland")
    assert not otherland.institution_kinds.exists()
    assert not otherland.parties.exists()
    assert "Otherland: no executive institution" in output


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


def test_institution_starting_after_the_date_is_not_imported(testland, importer):
    output = run_import(testland, "2014-06-01")

    assert {branch for branch, *_ in institutions(importer)} == {"judiciary"}
    assert "'Government' has no records valid on or before 2014-06-01" in output
    assert "'Parliament' has no records valid on or before 2014-06-01" in output


def test_overlapping_cabinets_are_an_error(testland_copy, importer):
    edit_rows(
        testland_copy / "cabinet.csv", {"name": "Cabinet B"}, valid_from="2019-01-01"
    )

    assert "'Government': 2 records are valid on 2019-06-01" in import_error(
        testland_copy, "2019-06-01"
    )


def test_more_than_one_institution_per_branch_is_an_error(testland_copy, importer):
    add_row(
        testland_copy / "institution.csv",
        {"name": "Parliament"},
        institution_id=str(uuid4()),
        name="Senate",
    )

    assert "Testland: 2 legislative institutions ('Parliament', 'Senate')" in (
        import_error(testland_copy)
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

    assert parties(importer) == {"Red"}


def test_party_whose_position_ended_before_the_cabinet_is_skipped(
    testland_copy, importer
):
    # Cabinet B ended on 2024-01-01, Blue's last position now ends in 2022
    edit_rows(
        testland_copy / "party-position.csv",
        {"party_position_id": BLUE_CURRENT_POSITION},
        valid_to="2022-01-01",
    )

    run_import(testland_copy)

    assert parties(importer) == {"Red"}


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

    run_import(testland_copy, "2010-01-01")  # the other positions start in 2015

    assert parties(importer) == {"Grey"}


def test_overlapping_positions_are_an_error(testland_copy, importer):
    edit_rows(
        testland_copy / "party-position.csv",
        {"party_position_id": RED_FIRST_POSITION},
        valid_to="2021-01-01",
    )

    assert "positions of 'Red': 2 records are valid on 2020-06-01" in import_error(
        testland_copy, "2020-06-01"
    )


def test_more_parties_than_seats_is_a_warning(testland_copy, importer):
    edit_rows(testland_copy / "chamber.csv", {"size": "100"}, size="2")

    assert "2 parties for 2 seats in 'Parliament'" in run_import(testland_copy)


# Running it again


def test_second_run_adds_nothing(testland, importer):
    run_import(testland)
    counts = record_counts()

    run_import(testland)

    assert record_counts() == counts


def test_existing_records_are_kept_and_the_rest_added(testland, importer):
    country = create_testland(importer)
    Party.objects.create(country=country, label="Red")

    run_import(testland)

    assert UserSettings.objects.filter(user=importer, label="Testland").count() == 1
    assert sorted(country.parties.values_list("label", flat=True)) == ["Blue", "Red"]
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


# Missing files


def test_missing_court_imports_the_rest_and_warns(testland_copy, importer):
    (testland_copy / "court.csv").unlink()

    output = run_import(testland_copy)

    assert {branch for branch, *_ in institutions(importer)} == {
        "executive",
        "legislative",
    }
    assert "court.csv: file is missing" in output
    assert "no judiciary institution" in output


@pytest.mark.parametrize(
    "file_name", ["cabinet.csv", "chamber.csv", "court.csv", "party-position.csv"]
)
def test_missing_optional_file_is_a_warning(testland_copy, importer, file_name):
    (testland_copy / file_name).unlink()

    assert f"{file_name}: file is missing, nothing imported from it." in run_import(
        testland_copy
    )


def test_without_a_chamber_parties_are_imported_without_positions(
    testland_copy, importer
):
    (testland_copy / "chamber.csv").unlink()

    output = run_import(testland_copy)

    assert parties(importer) == {"Red", "Blue"}
    assert positions(importer) == set()
    assert "no chamber, party positions not imported" in output


@pytest.mark.parametrize("file_name", ["country.csv", "institution.csv"])
def test_missing_required_file_is_an_error(testland_copy, importer, file_name):
    (testland_copy / file_name).unlink()

    assert f"{file_name}: required file is missing." in import_error(testland_copy)


# File format


def test_quoted_values_may_contain_commas(testland_copy, importer):
    edit_rows(testland_copy / "country.csv", {"name": "Testland"}, name="Test, land")

    run_import(testland_copy)

    assert UserSettings.objects.filter(user=importer, label="Test, land").exists()


def test_byte_order_mark_is_accepted(testland_copy, importer):
    path = testland_copy / "country.csv"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())

    run_import(testland_copy)

    assert UserSettings.objects.filter(user=importer, label="Testland").exists()


def test_other_files_in_the_folder_are_ignored(testland_copy, importer):
    (testland_copy / "README.md").write_bytes(b"# notes")

    output = run_import(testland_copy)

    assert "README" not in output
    assert parties(importer) == {"Red", "Blue"}


def test_non_utf8_file_is_an_error(testland_copy, importer):
    path = testland_copy / "country.csv"
    path.write_bytes(
        path.read_bytes().replace(b"Testland", "Testländ".encode("latin-1"))
    )

    assert "country.csv: not a UTF-8 text file." in import_error(testland_copy)


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
    testland_copy, importer, file_name, where, changes, problem
):
    edit_rows(testland_copy / file_name, where, **changes)
    counts = record_counts()

    assert problem in import_error(testland_copy)
    assert record_counts() == counts


def test_every_problem_is_reported_at_once(testland_copy, importer):
    edit_rows(testland_copy / "cabinet.csv", {"name": "Cabinet B"}, size="abc")
    edit_rows(
        testland_copy / "party-position.csv",
        {"party_position_id": RED_FIRST_POSITION},
        position="coalition",
    )

    message = import_error(testland_copy)

    assert "cabinet.csv line 3:" in message
    assert "party-position.csv line 2:" in message


def test_duplicate_id_is_an_error(testland_copy, importer):
    add_row(testland_copy / "cabinet.csv", {"name": "Cabinet A"})

    assert (
        "cabinet.csv: duplicate cabinet_id ca000000-0000-4000-8000-000000000001."
        in import_error(testland_copy)
    )


def test_broken_reference_is_an_error(testland_copy, importer):
    edit_rows(
        testland_copy / "party-position.csv",
        {"party_position_id": GREY_POSITION},
        political_party_id=UNKNOWN_PARTY,
    )

    assert (
        f"party-position.csv: political_party_id {UNKNOWN_PARTY} not found in "
        "political-party.csv." in import_error(testland_copy)
    )


def test_reference_to_a_missing_file_is_an_error(testland_copy, importer):
    (testland_copy / "political-party.csv").unlink()

    assert "not found in political-party.csv" in import_error(testland_copy)


def test_invalid_rows_are_not_also_reported_as_broken_references(
    testland_copy, importer
):
    edit_rows(testland_copy / "country.csv", {"name": "Testland"}, country_id="x")

    message = import_error(testland_copy)

    assert "country.csv line 2: country_id:" in message
    assert "not found" not in message


def test_record_rejected_by_a_model_rolls_back_the_whole_import(
    testland_copy, importer
):
    # the contract accepts the name, the 50-character Party.label does not;
    # Blue comes after Red, so records were already saved when it fails
    edit_rows(testland_copy / "political-party.csv", {"name": "Blue"}, name="B" * 51)
    counts = record_counts()

    assert "B" * 51 in import_error(testland_copy)
    assert record_counts() == counts


def test_institution_name_taken_by_another_branch_is_an_error(testland, importer):
    InstitutionKind.objects.create(
        country=create_testland(importer),
        institution_name="Parliament",
        branch=InstitutionBranch.EXECUTIVE,
    )
    counts = record_counts()

    assert "already exists" in import_error(testland)
    assert record_counts() == counts


# Command arguments


def test_as_of_defaults_to_today(testland, importer):
    assert str(timezone.localdate()) in run(testland, "--username=importer")


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
