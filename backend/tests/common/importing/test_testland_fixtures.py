"""Keeps Testland a valid delivery that covers the cases the import tests rely on."""

from collections import Counter

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

from common.importing import CONTRACT_FILES


def test_has_exactly_the_contract_files(testland_dir):
    assert {path.name for path in testland_dir.glob("*.csv")} == set(CONTRACT_FILES)


def test_is_a_complete_delivery(testland_delivery):
    assert testland_delivery.warnings == ()


@pytest.mark.parametrize(
    "contract,count",
    [
        (Country, 1),
        (Institution, 3),
        (Cabinet, 2),
        (Chamber, 2),
        (Court, 1),
        (PoliticalParty, 4),
        (PartyPosition, 5),
    ],
)
def test_row_counts(testland_delivery, contract, count):
    assert len(testland_delivery.of(contract)) == count


def test_one_institution_per_branch(testland_delivery):
    branches = Counter(
        institution.branch for institution in testland_delivery.of(Institution)
    )
    assert branches == {"executive": 1, "legislative": 1, "judicial": 1}


@pytest.mark.parametrize(
    "contract,institution_name",
    [
        (Cabinet, "Government"),
        (Chamber, "Parliament"),
        (Court, "Constitutional Court"),
    ],
)
def test_instances_belong_to_the_matching_institution(
    testland_delivery, contract, institution_name
):
    names = {i.institution_id: i.name for i in testland_delivery.of(Institution)}
    assert {names[r.institution_id] for r in testland_delivery.of(contract)} == {
        institution_name
    }


def test_time_windows_start_before_they_end(testland_delivery):
    for contract in (Cabinet, Chamber, Court, PartyPosition):
        for record in testland_delivery.of(contract):
            if record.valid_from and record.valid_to:
                assert record.valid_from < record.valid_to, record


def test_parties_cover_the_filter_cases(testland_delivery):
    parties = {party.name: party for party in testland_delivery.of(PoliticalParty)}
    with_position = {p.political_party_id for p in testland_delivery.of(PartyPosition)}

    assert parties["Red"].political_party_id in with_position
    assert parties["Blue"].political_party_id in with_position
    assert parties["Green"].political_party_id not in with_position
    assert parties["Grey"].date_dissolved is not None
