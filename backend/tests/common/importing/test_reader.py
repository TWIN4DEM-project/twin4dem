import re
from datetime import date

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from twin4dem_data_contracts.models import (
    Cabinet,
    Chamber,
    Country,
    Court,
    PoliticalParty,
)

from common.importing import REQUIRED_FILES, DataImportError, read_delivery

GREY_ID = "a0000000-0000-4000-8000-000000000004"
UNKNOWN_ID = "a0000000-0000-4000-8000-000000000009"


def read_bytes(storage: Storage, name: str) -> bytes:
    with storage.open(name, "rb") as stream:
        return stream.read()


def put(storage: Storage, name: str, content: bytes) -> None:
    """Replace a file: Storage.save() would rename the new file instead."""
    if storage.exists(name):
        storage.delete(name)
    storage.save(name, ContentFile(content))


def edit(storage: Storage, name: str, old: str, new: str) -> None:
    """Replace the first occurrence of `old` in a file."""
    text = read_bytes(storage, name).decode()
    assert old in text
    put(storage, name, text.replace(old, new, 1).encode())


def import_error(storage: Storage) -> str:
    with pytest.raises(DataImportError) as error:
        read_delivery(storage)
    return str(error.value)


def test_values_are_typed_by_the_contract(testland_storage):
    cabinets = read_delivery(testland_storage).of(Cabinet)

    cabinet_b = next(cabinet for cabinet in cabinets if cabinet.name == "Cabinet B")
    assert cabinet_b.size == 15
    assert cabinet_b.valid_from == date(2020, 1, 1)


def test_empty_cells_are_missing_values(testland_storage):
    delivery = read_delivery(testland_storage)

    blue = next(p for p in delivery.of(PoliticalParty) if p.name == "Blue")
    assert blue.date_founded is None
    assert [c.valid_to for c in delivery.of(Chamber) if c.size == 100] == [None]


def test_quoted_values_may_contain_commas(testland_storage):
    edit(testland_storage, "country.csv", ",Testland,", ',"Test, land",')

    assert read_delivery(testland_storage).of(Country)[0].name == "Test, land"


def test_byte_order_mark_is_accepted(testland_storage):
    content = read_bytes(testland_storage, "country.csv")
    put(testland_storage, "country.csv", b"\xef\xbb\xbf" + content)

    assert read_delivery(testland_storage).of(Country)[0].name == "Testland"


def test_other_files_are_ignored(testland_storage):
    testland_storage.save("README.md", ContentFile(b"# notes"))

    assert read_delivery(testland_storage).warnings == ()


@pytest.mark.parametrize("file_name", sorted(REQUIRED_FILES))
def test_missing_required_file_is_an_error(testland_storage, file_name):
    testland_storage.delete(file_name)

    assert f"{file_name}: required file is missing." in import_error(testland_storage)


@pytest.mark.parametrize(
    "file_name", ["cabinet.csv", "chamber.csv", "court.csv", "party-position.csv"]
)
def test_missing_optional_file_is_a_warning(testland_storage, file_name):
    testland_storage.delete(file_name)

    delivery = read_delivery(testland_storage)
    assert delivery.warnings == (
        f"{file_name}: file is missing, nothing imported from it.",
    )


def test_missing_file_has_no_records(testland_storage):
    testland_storage.delete("court.csv")

    assert read_delivery(testland_storage).of(Court) == []


def test_invalid_value_reports_file_line_and_field(testland_storage):
    edit(testland_storage, "cabinet.csv", ",15,", ",abc,")

    assert re.search(
        r"cabinet\.csv line 3: size: Input should be a valid integer",
        import_error(testland_storage),
    )


def test_missing_value_reports_file_line_and_field(testland_storage):
    edit(testland_storage, "country.csv", ",Testland,", ",,")

    assert "country.csv line 2: name:" in import_error(testland_storage)


def test_value_outside_the_contract_choices_is_an_error(testland_storage):
    edit(testland_storage, "party-position.csv", ",opposition,", ",coalition,")

    assert "party-position.csv line 2: position:" in import_error(testland_storage)


def test_every_problem_is_reported_at_once(testland_storage):
    edit(testland_storage, "cabinet.csv", ",15,", ",abc,")
    edit(testland_storage, "party-position.csv", ",opposition,", ",coalition,")

    message = import_error(testland_storage)
    assert "cabinet.csv line 3:" in message
    assert "party-position.csv line 2:" in message


def test_non_utf8_file_is_an_error(testland_storage):
    content = read_bytes(testland_storage, "country.csv").decode()
    put(
        testland_storage,
        "country.csv",
        content.replace("Testland", "Testländ").encode("latin-1"),
    )

    assert "country.csv: not a UTF-8 text file." in import_error(testland_storage)


def test_duplicate_id_is_an_error(testland_storage):
    content = read_bytes(testland_storage, "cabinet.csv")
    first_row = content.splitlines(keepends=True)[1]
    put(testland_storage, "cabinet.csv", content + first_row)

    assert (
        "cabinet.csv: duplicate cabinet_id ca000000-0000-4000-8000-000000000001."
        in import_error(testland_storage)
    )


def test_broken_reference_is_an_error(testland_storage):
    edit(testland_storage, "party-position.csv", GREY_ID, UNKNOWN_ID)

    assert (
        f"party-position.csv: political_party_id {UNKNOWN_ID} not found in "
        "political-party.csv." in import_error(testland_storage)
    )


def test_reference_to_a_missing_file_is_an_error(testland_storage):
    testland_storage.delete("political-party.csv")

    assert re.search(
        r"party-position\.csv: political_party_id \S+ not found in "
        r"political-party\.csv",
        import_error(testland_storage),
    )


def test_invalid_rows_are_not_also_reported_as_broken_references(testland_storage):
    edit(testland_storage, "country.csv", "c0000000-", "not-a-uuid-")

    message = import_error(testland_storage)
    assert "country.csv line 2: country_id:" in message
    assert "not found" not in message
