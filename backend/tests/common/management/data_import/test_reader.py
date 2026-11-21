import re
from datetime import date
from pathlib import Path

import pytest
from twin4dem_data_contracts.models import (
    Cabinet,
    Chamber,
    Country,
    Court,
    PoliticalParty,
)

from common.management.commands._data_import._exceptions import DataImportError
from common.management.commands._data_import._reader import (
    REQUIRED_FILES,
    read_delivery,
)

GREY_ID = "a0000000-0000-4000-8000-000000000004"
UNKNOWN_ID = "a0000000-0000-4000-8000-000000000009"


def edit(folder: Path, name: str, old: str, new: str) -> None:
    """Replace the first occurrence of `old` in a file."""
    path = folder / name
    text = path.read_bytes().decode()
    assert old in text
    path.write_bytes(text.replace(old, new, 1).encode())


def import_error(folder: Path) -> str:
    with pytest.raises(DataImportError) as error:
        read_delivery(folder)
    return str(error.value)


def test_values_are_typed_by_the_contract(testland_copy):
    cabinets = read_delivery(testland_copy).of(Cabinet)

    cabinet_b = next(cabinet for cabinet in cabinets if cabinet.name == "Cabinet B")
    assert cabinet_b.size == 15
    assert cabinet_b.valid_from == date(2020, 1, 1)


def test_empty_cells_are_missing_values(testland_copy):
    delivery = read_delivery(testland_copy)

    blue = next(p for p in delivery.of(PoliticalParty) if p.name == "Blue")
    assert blue.date_founded is None
    assert [c.valid_to for c in delivery.of(Chamber) if c.size == 100] == [None]


def test_quoted_values_may_contain_commas(testland_copy):
    edit(testland_copy, "country.csv", ",Testland,", ',"Test, land",')

    assert read_delivery(testland_copy).of(Country)[0].name == "Test, land"


def test_byte_order_mark_is_accepted(testland_copy):
    path = testland_copy / "country.csv"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())

    assert read_delivery(testland_copy).of(Country)[0].name == "Testland"


def test_other_files_are_ignored(testland_copy):
    (testland_copy / "README.md").write_bytes(b"# notes")

    assert read_delivery(testland_copy).warnings == ()


@pytest.mark.parametrize("file_name", sorted(REQUIRED_FILES))
def test_missing_required_file_is_an_error(testland_copy, file_name):
    (testland_copy / file_name).unlink()

    assert f"{file_name}: required file is missing." in import_error(testland_copy)


@pytest.mark.parametrize(
    "file_name", ["cabinet.csv", "chamber.csv", "court.csv", "party-position.csv"]
)
def test_missing_optional_file_is_a_warning(testland_copy, file_name):
    (testland_copy / file_name).unlink()

    delivery = read_delivery(testland_copy)
    assert delivery.warnings == (
        f"{file_name}: file is missing, nothing imported from it.",
    )


def test_missing_file_has_no_records(testland_copy):
    (testland_copy / "court.csv").unlink()

    assert read_delivery(testland_copy).of(Court) == []


def test_invalid_value_reports_file_line_and_field(testland_copy):
    edit(testland_copy, "cabinet.csv", ",15,", ",abc,")

    assert re.search(
        r"cabinet\.csv line 3: size: Input should be a valid integer",
        import_error(testland_copy),
    )


def test_missing_value_reports_file_line_and_field(testland_copy):
    edit(testland_copy, "country.csv", ",Testland,", ",,")

    assert "country.csv line 2: name:" in import_error(testland_copy)


def test_value_outside_the_contract_choices_is_an_error(testland_copy):
    edit(testland_copy, "party-position.csv", ",opposition,", ",coalition,")

    assert "party-position.csv line 2: position:" in import_error(testland_copy)


def test_every_problem_is_reported_at_once(testland_copy):
    edit(testland_copy, "cabinet.csv", ",15,", ",abc,")
    edit(testland_copy, "party-position.csv", ",opposition,", ",coalition,")

    message = import_error(testland_copy)
    assert "cabinet.csv line 3:" in message
    assert "party-position.csv line 2:" in message


def test_non_utf8_file_is_an_error(testland_copy):
    path = testland_copy / "country.csv"
    content = path.read_bytes().decode()
    path.write_bytes(content.replace("Testland", "Testländ").encode("latin-1"))

    assert "country.csv: not a UTF-8 text file." in import_error(testland_copy)


def test_duplicate_id_is_an_error(testland_copy):
    path = testland_copy / "cabinet.csv"
    content = path.read_bytes()
    first_row = content.splitlines(keepends=True)[1]
    path.write_bytes(content + first_row)

    assert (
        "cabinet.csv: duplicate cabinet_id ca000000-0000-4000-8000-000000000001."
        in import_error(testland_copy)
    )


def test_broken_reference_is_an_error(testland_copy):
    edit(testland_copy, "party-position.csv", GREY_ID, UNKNOWN_ID)

    assert (
        f"party-position.csv: political_party_id {UNKNOWN_ID} not found in "
        "political-party.csv." in import_error(testland_copy)
    )


def test_reference_to_a_missing_file_is_an_error(testland_copy):
    (testland_copy / "political-party.csv").unlink()

    assert re.search(
        r"party-position\.csv: political_party_id \S+ not found in "
        r"political-party\.csv",
        import_error(testland_copy),
    )


def test_invalid_rows_are_not_also_reported_as_broken_references(testland_copy):
    edit(testland_copy, "country.csv", "c0000000-", "not-a-uuid-")

    message = import_error(testland_copy)
    assert "country.csv line 2: country_id:" in message
    assert "not found" not in message
