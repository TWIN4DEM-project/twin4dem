from datetime import date
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel
from twin4dem_data_contracts.models import (
    Cabinet,
    Chamber,
    Country,
    Court,
    Institution,
    PartyPosition,
    PoliticalParty,
)

from common.importing import (
    CountrySelection,
    DataImportError,
    Delivery,
    SelectedInstitution,
    select,
)
from common.models import InstitutionBranch

AS_OF = date(2025, 6, 1)
RED_FIRST_POSITION = UUID("b0000000-0000-4000-8000-000000000001")
BLUE_CURRENT_POSITION = UUID("b0000000-0000-4000-8000-000000000004")
GREY_POSITION = UUID("b0000000-0000-4000-8000-000000000005")


def select_one(delivery: Delivery, as_of: date = AS_OF) -> CountrySelection:
    [selection] = select(delivery, as_of)
    return selection


def matches(row: BaseModel, where: dict) -> bool:
    return all(getattr(row, name) == value for name, value in where.items())


def edited(delivery: Delivery, contract, where: dict, **changes) -> Delivery:
    """`delivery` with the matching rows of `contract` changed."""
    rows = [
        row.model_copy(update=changes) if matches(row, where) else row
        for row in delivery.of(contract)
    ]
    return Delivery({**delivery.records, contract: rows})


def copied(delivery: Delivery, contract, where: dict, **changes) -> Delivery:
    """`delivery` with a changed copy of the matching row of `contract` added."""
    [row] = [row for row in delivery.of(contract) if matches(row, where)]
    rows = [*delivery.of(contract), row.model_copy(update=changes)]
    return Delivery({**delivery.records, contract: rows})


def institution(
    selection: CountrySelection, branch: InstitutionBranch
) -> SelectedInstitution:
    return next(s for s in selection.institutions if s.branch == branch)


def positions(selection: CountrySelection) -> dict[str, str]:
    return {s.party.name: s.position.position for s in selection.parties}


def test_one_selection_per_country(testland_delivery):
    assert [s.country.name for s in select(testland_delivery, AS_OF)] == ["Testland"]


def test_countries_get_only_their_own_data(testland_delivery):
    delivery = copied(
        testland_delivery,
        Country,
        {"name": "Testland"},
        country_id=uuid4(),
        name="Otherland",
    )

    other = next(s for s in select(delivery, AS_OF) if s.country.name == "Otherland")
    assert other.institutions == other.parties == other.skipped_parties == ()
    assert other.warnings == (
        "Otherland: no executive institution, imported without one.",
        "Otherland: no legislative institution, imported without one.",
        "Otherland: no judiciary institution, imported without one.",
    )


def test_branches_are_translated_to_twin4dem(testland_delivery):
    selection = select_one(testland_delivery)

    assert {s.branch for s in selection.institutions} == set(InstitutionBranch)


@pytest.mark.parametrize(
    "as_of,cabinet",
    [
        (date(2018, 6, 1), "Cabinet A"),
        (date(2019, 12, 31), "Cabinet A"),
        (date(2020, 1, 1), "Cabinet B"),  # the end day of Cabinet A is excluded
        (date(2025, 6, 1), "Cabinet B"),  # none valid: the most recent
    ],
)
def test_cabinet_valid_on_the_date_else_the_most_recent(
    testland_delivery, as_of, cabinet
):
    selection = select_one(testland_delivery, as_of)

    assert institution(selection, InstitutionBranch.EXECUTIVE).instance.name == cabinet


def test_chamber_and_court_follow_the_same_rule(testland_delivery):
    selection = select_one(testland_delivery, date(2018, 6, 1))

    assert institution(selection, InstitutionBranch.LEGISLATIVE).instance.size == 90
    assert institution(selection, InstitutionBranch.JUDICIARY).instance.size == 9


def test_records_starting_after_the_date_are_ignored(testland_delivery):
    selection = select_one(testland_delivery, date(2014, 6, 1))

    assert {s.branch for s in selection.institutions} == {InstitutionBranch.JUDICIARY}
    assert [i.name for i in selection.skipped_institutions] == [
        "Government",
        "Parliament",
    ]


def test_overlapping_time_windows_are_an_error(testland_delivery):
    delivery = edited(
        testland_delivery, Cabinet, {"name": "Cabinet B"}, valid_from=date(2019, 1, 1)
    )

    with pytest.raises(DataImportError, match="'Government': 2 records are valid on"):
        select(delivery, date(2019, 6, 1))


def test_more_than_one_institution_per_branch_is_an_error(testland_delivery):
    delivery = copied(
        testland_delivery,
        Institution,
        {"name": "Parliament"},
        institution_id=uuid4(),
        name="Senate",
    )

    with pytest.raises(
        DataImportError,
        match=r"Testland: 2 legislative institutions \('Parliament', 'Senate'\)",
    ):
        select(delivery, AS_OF)


def test_institution_without_records_is_left_out(testland_delivery):
    delivery = Delivery({**testland_delivery.records, Court: []})

    warnings = select_one(delivery).warnings
    assert (
        "Testland: 'Constitutional Court' has no records valid on or before "
        "2025-06-01, not imported." in warnings
    )
    assert "Testland: no judiciary institution, imported without one." in warnings


def test_reference_date_is_the_import_date_while_the_cabinet_is_valid(
    testland_delivery,
):
    selection = select_one(testland_delivery, date(2018, 6, 1))

    assert selection.reference_date == date(2018, 6, 1)


def test_reference_date_is_the_last_day_of_an_ended_cabinet(testland_delivery):
    # the most recent cabinet, Cabinet B, ended on 2024-01-01
    assert select_one(testland_delivery).reference_date == date(2023, 12, 31)


def test_reference_date_without_cabinet_is_the_import_date(testland_delivery):
    delivery = Delivery({**testland_delivery.records, Cabinet: []})

    assert select_one(delivery).reference_date == AS_OF


def test_party_gets_its_position_on_the_reference_date(testland_delivery):
    assert positions(select_one(testland_delivery)) == {
        "Red": "majority",
        "Blue": "opposition",
    }


def test_position_ended_before_the_reference_date_is_skipped(testland_delivery):
    # Blue's last position now ends before Cabinet B does, so Blue is not part
    # of the selected cabinet's period
    delivery = edited(
        testland_delivery,
        PartyPosition,
        {"party_position_id": BLUE_CURRENT_POSITION},
        valid_to=date(2022, 1, 1),
    )

    selection = select_one(delivery)
    assert "Blue" not in positions(selection)
    assert "Blue" in [p.name for p in selection.skipped_parties]


def test_overlapping_positions_are_an_error(testland_delivery):
    delivery = edited(
        testland_delivery,
        PartyPosition,
        {"party_position_id": RED_FIRST_POSITION},
        valid_to=date(2021, 1, 1),
    )

    with pytest.raises(
        DataImportError, match="positions of 'Red': 2 records are valid on 2020-06-01"
    ):
        select(delivery, date(2020, 6, 1))


def test_party_gets_the_position_valid_on_the_date(testland_delivery):
    assert positions(select_one(testland_delivery, date(2018, 6, 1))) == {
        "Red": "opposition",
        "Blue": "majority",
        "Grey": "opposition",
    }


def test_party_without_position_is_skipped(testland_delivery):
    selection = select_one(testland_delivery)

    assert "Green" in [p.name for p in selection.skipped_parties]


@pytest.mark.parametrize(
    "as_of,imported", [(date(2019, 5, 31), True), (date(2019, 6, 1), False)]
)
def test_party_is_skipped_from_its_dissolution_day(testland_delivery, as_of, imported):
    # Grey's position stays open, so only its dissolution on 2019-06-01 counts
    delivery = edited(
        testland_delivery,
        PartyPosition,
        {"party_position_id": GREY_POSITION},
        valid_to=None,
    )

    assert ("Grey" in positions(select_one(delivery, as_of))) is imported


def test_party_not_founded_yet_is_skipped(testland_delivery):
    delivery = edited(
        testland_delivery,
        PoliticalParty,
        {"name": "Red"},
        date_founded=date(2021, 1, 1),
    )

    assert "Red" not in positions(select_one(delivery, date(2020, 6, 1)))


def test_explicit_independent_position_is_kept(testland_delivery):
    delivery = edited(
        testland_delivery,
        PartyPosition,
        {"party_position_id": BLUE_CURRENT_POSITION},
        position="independent",
    )

    assert positions(select_one(delivery))["Blue"] == "independent"


def test_position_without_start_counts_from_the_beginning(testland_delivery):
    delivery = edited(
        testland_delivery,
        PartyPosition,
        {"party_position_id": GREY_POSITION},
        valid_from=None,
    )

    assert positions(select_one(delivery, date(2010, 1, 1))) == {"Grey": "opposition"}


def test_complete_country_only_warns_about_skipped_parties(testland_delivery):
    selection = select_one(testland_delivery)

    assert [p.name for p in selection.skipped_parties] == ["Green", "Grey"]
    assert selection.warnings == (
        "Testland: 2 of 4 parties skipped: no position on 2023-12-31, "
        "or not active on that date.",
    )


def test_more_parties_than_seats_is_a_warning(testland_delivery):
    delivery = edited(testland_delivery, Chamber, {"size": 100}, size=2)

    assert (
        "Testland: 2 parties for 2 seats in 'Parliament', the seat model gives "
        "each party only its leader." in select_one(delivery).warnings
    )
