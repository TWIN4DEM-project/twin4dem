from collections import Counter
from datetime import date
from uuid import uuid4

import pytest
from twin4dem_data_contracts.models import Chamber, PoliticalParty
from twin4dem_data_contracts.models import Country as CountryRecord

from common.management.commands._data_import._exceptions import DataImportError
from common.management.commands._data_import._reader import Delivery
from common.management.commands._data_import._selection import select
from common.management.commands._data_import._writer import WriteResult, write
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

AS_OF = date(2025, 6, 1)


@pytest.fixture
def importer(django_user_model):
    return django_user_model.objects.create_user(username="importer")


def run(delivery: Delivery, user, as_of: date = AS_OF) -> WriteResult:
    return write(select(delivery, as_of), user)


def by_name(counter: Counter) -> dict[str, int]:
    return {model.__name__: count for model, count in counter.items()}


def stored(user) -> dict[str, int]:
    """How many records of each model `user` owns."""
    return {
        "UserSettings": UserSettings.objects.filter(user=user).count(),
        "Country": Country.objects.filter(user_settings__user=user).count(),
        "InstitutionKind": InstitutionKind.objects.filter(
            country__user_settings__user=user
        ).count(),
        "Institution": Institution.objects.filter(
            kind__country__user_settings__user=user
        ).count(),
        "Party": Party.objects.filter(country__user_settings__user=user).count(),
        "PartyPosition": PartyPosition.objects.filter(
            party__country__user_settings__user=user
        ).count(),
    }


def create_testland(user) -> Country:
    settings = UserSettings.objects.create(user=user, label="Testland")
    return Country.objects.create(user_settings=settings, name="Testland")


def test_creates_the_country_under_settings_named_after_it(testland_delivery, importer):
    run(testland_delivery, importer)

    settings = UserSettings.objects.get(user=importer, label="Testland")
    assert settings.countries.get().name == "Testland"
    assert settings.timelines.exists()  # created by the existing signal


def test_creates_one_institution_per_branch(testland_delivery, importer):
    run(testland_delivery, importer)

    institutions = Institution.objects.filter(
        kind__country__user_settings__user=importer
    )
    assert {
        i.kind.branch: (i.kind.institution_name, i.label, i.size) for i in institutions
    } == {
        InstitutionBranch.EXECUTIVE: ("Government", "Cabinet B", 15),
        InstitutionBranch.LEGISLATIVE: ("Parliament", "Parliament", 100),
        InstitutionBranch.JUDICIARY: (
            "Constitutional Court",
            "Constitutional Court",
            9,
        ),
    }


def test_records_are_validated_by_the_model_before_saving(testland_delivery, importer):
    run(testland_delivery, importer)

    # Institution.clean() fills in the payload defaults of its branch
    cabinet = Institution.objects.get(
        kind__country__user_settings__user=importer,
        kind__branch=InstitutionBranch.EXECUTIVE,
    )
    assert cabinet.payload == {"connectivity_degree": 3, "probability_for": None}


def test_creates_parties_with_their_position_in_the_chamber(
    testland_delivery, importer
):
    run(testland_delivery, importer)

    positions = PartyPosition.objects.filter(
        party__country__user_settings__user=importer
    )
    assert {p.party.label: (p.position, p.chamber.label) for p in positions} == {
        "Red": ("majority", "Parliament"),
        "Blue": ("opposition", "Parliament"),
    }


def test_reports_what_it_created(testland_delivery, importer):
    result = run(testland_delivery, importer)

    assert by_name(result.created) == {
        "UserSettings": 1,
        "Country": 1,
        "InstitutionKind": 3,
        "Institution": 3,
        "Party": 2,
        "PartyPosition": 2,
    }
    assert result.skipped == Counter()
    assert result.warnings == []


def test_second_run_changes_nothing(testland_delivery, importer):
    first = run(testland_delivery, importer)
    before = stored(importer)

    second = run(testland_delivery, importer)

    assert stored(importer) == before
    assert second.created == Counter()
    assert second.skipped == first.created


def test_existing_records_are_skipped_and_the_rest_added(testland_delivery, importer):
    Party.objects.create(country=create_testland(importer), label="Red")

    result = run(testland_delivery, importer)

    assert result.skipped == Counter({UserSettings: 1, Country: 1, Party: 1})
    assert result.created[Party] == 1  # Blue


def test_existing_institution_of_a_kind_is_kept(testland_delivery, importer):
    run(testland_delivery, importer)  # Cabinet B

    result = run(testland_delivery, importer, date(2018, 6, 1))  # selects Cabinet A

    cabinet = Institution.objects.get(
        kind__country__user_settings__user=importer,
        kind__branch=InstitutionBranch.EXECUTIVE,
    )
    assert cabinet.label == "Cabinet B"
    assert result.created[Institution] == 0


def test_existing_position_in_the_chamber_is_kept(testland_delivery, importer):
    run(testland_delivery, importer)  # Red: majority

    run(testland_delivery, importer, date(2018, 6, 1))  # selects Red: opposition

    red = PartyPosition.objects.get(
        party__country__user_settings__user=importer, party__label="Red"
    )
    assert red.position == "majority"


def test_without_a_chamber_party_positions_are_not_imported(
    testland_delivery, importer
):
    delivery = Delivery({**testland_delivery.records, Chamber: []})

    result = run(delivery, importer)

    assert result.created[Party] == 2
    assert result.created[PartyPosition] == 0
    assert result.warnings == ["Testland: no chamber, party positions not imported."]


def test_each_country_gets_its_own_settings(testland_delivery, importer):
    [testland] = testland_delivery.of(CountryRecord)
    other = testland.model_copy(update={"country_id": uuid4(), "name": "Otherland"})
    delivery = Delivery({**testland_delivery.records, CountryRecord: [testland, other]})

    run(delivery, importer)

    labels = UserSettings.objects.filter(user=importer).values_list("label", flat=True)
    assert set(labels) == {"default", "Testland", "Otherland"}


def test_invalid_record_stops_the_import_and_saves_nothing(testland_delivery, importer):
    long_name = "R" * 51
    parties = [
        party.model_copy(update={"name": long_name}) if party.name == "Red" else party
        for party in testland_delivery.of(PoliticalParty)
    ]
    delivery = Delivery({**testland_delivery.records, PoliticalParty: parties})

    with pytest.raises(
        DataImportError,
        match=rf"Party \(country=Testland, label={long_name}\): "
        r"Ensure this value has at most 50 characters",
    ):
        run(delivery, importer)
    assert not UserSettings.objects.filter(user=importer, label="Testland").exists()


def test_institution_name_taken_by_another_branch_is_an_error(
    testland_delivery, importer
):
    InstitutionKind.objects.create(
        country=create_testland(importer),
        institution_name="Parliament",
        branch=InstitutionBranch.EXECUTIVE,
    )

    with pytest.raises(
        DataImportError, match=r"InstitutionKind \(.*institution_name=Parliament"
    ):
        run(testland_delivery, importer)
