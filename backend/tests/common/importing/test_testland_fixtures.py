"""Keeps the Testland fixtures valid against the data contracts."""

import csv
from collections import Counter
from pathlib import Path

import pytest
from twin4dem_data_contracts.models import (
    Cabinet,
    Chamber,
    Country,
    Court,
    Institution,
    PartyPosition,
    PoliticalParty,
)

CONTRACTS = {
    "country.csv": (Country, "country_id", 1),
    "institution.csv": (Institution, "institution_id", 3),
    "cabinet.csv": (Cabinet, "cabinet_id", 2),
    "chamber.csv": (Chamber, "chamber_id", 2),
    "court.csv": (Court, "court_id", 1),
    "political-party.csv": (PoliticalParty, "political_party_id", 4),
    "party-position.csv": (PartyPosition, "party_position_id", 5),
}


def parse(directory: Path, file_name: str) -> list:
    model, _, _ = CONTRACTS[file_name]
    with (directory / file_name).open(newline="", encoding="utf-8") as stream:
        return [
            model(**{key: value or None for key, value in row.items()})
            for row in csv.DictReader(stream)
        ]


@pytest.fixture
def testland(testland_dir) -> dict[str, list]:
    return {file_name: parse(testland_dir, file_name) for file_name in CONTRACTS}


def ids(records: list, field: str) -> set:
    return {getattr(record, field) for record in records}


def test_delivery_has_exactly_the_contract_files(testland_dir):
    csv_files = {path.name for path in testland_dir.glob("*.csv")}
    assert csv_files == set(CONTRACTS)


@pytest.mark.parametrize("file_name", CONTRACTS)
def test_rows_satisfy_the_contract(testland, file_name):
    _, _, expected_rows = CONTRACTS[file_name]
    assert len(testland[file_name]) == expected_rows


@pytest.mark.parametrize("file_name", CONTRACTS)
def test_ids_are_unique(testland, file_name):
    _, id_field, _ = CONTRACTS[file_name]
    records = testland[file_name]
    assert len(ids(records, id_field)) == len(records)


@pytest.mark.parametrize(
    "file_name,field,target_file,target_field",
    [
        ("institution.csv", "country_id", "country.csv", "country_id"),
        ("cabinet.csv", "institution_id", "institution.csv", "institution_id"),
        ("chamber.csv", "institution_id", "institution.csv", "institution_id"),
        ("court.csv", "institution_id", "institution.csv", "institution_id"),
        ("political-party.csv", "country_id", "country.csv", "country_id"),
        (
            "party-position.csv",
            "political_party_id",
            "political-party.csv",
            "political_party_id",
        ),
    ],
)
def test_references_resolve(testland, file_name, field, target_file, target_field):
    known = ids(testland[target_file], target_field)
    assert ids(testland[file_name], field) <= known


def test_one_institution_per_branch(testland):
    branches = Counter(record.branch for record in testland["institution.csv"])
    assert branches == {"executive": 1, "legislative": 1, "judicial": 1}


@pytest.mark.parametrize(
    "file_name,institution_name",
    [
        ("cabinet.csv", "Government"),
        ("chamber.csv", "Parliament"),
        ("court.csv", "Constitutional Court"),
    ],
)
def test_instances_belong_to_the_matching_institution(
    testland, file_name, institution_name
):
    names = {
        record.institution_id: record.name for record in testland["institution.csv"]
    }
    assert {names[r.institution_id] for r in testland[file_name]} == {institution_name}


def test_time_windows_start_before_they_end(testland):
    for file_name in ("cabinet.csv", "chamber.csv", "court.csv", "party-position.csv"):
        for record in testland[file_name]:
            if record.valid_from and record.valid_to:
                assert record.valid_from < record.valid_to, (file_name, record)


def test_parties_cover_the_filter_cases(testland):
    parties = {party.name: party for party in testland["political-party.csv"]}
    with_position = ids(testland["party-position.csv"], "political_party_id")

    assert parties["Red"].political_party_id in with_position
    assert parties["Blue"].political_party_id in with_position
    assert parties["Green"].political_party_id not in with_position
    assert parties["Grey"].date_dissolved is not None


def test_copy_is_independent_of_the_original(testland_copy, testland_dir):
    (testland_copy / "court.csv").unlink()

    assert (testland_dir / "court.csv").exists()
    assert not (testland_copy / "court.csv").exists()
