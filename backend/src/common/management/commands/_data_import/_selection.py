import logging
from datetime import date, timedelta

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

from common.models import InstitutionBranch

from ._date_windows import current_or_latest, is_valid_on, valid_on
from ._exceptions import DataImportError

logger = logging.getLogger(__name__)

type Instance = Cabinet | Chamber | Court

BRANCHES: dict[str, tuple[InstitutionBranch, type[Instance]]] = {
    "executive": (InstitutionBranch.EXECUTIVE, Cabinet),
    "legislative": (InstitutionBranch.LEGISLATIVE, Chamber),
    "judicial": (InstitutionBranch.JUDICIARY, Court),
}


def select_institutions(
    records: dict[type[BaseModel], list[BaseModel]],
    country: Country,
    as_of: date,
) -> list[tuple[InstitutionBranch, Institution, Instance]]:
    """
    The institutions of `country`, each with its branch and its record valid on
    `as_of`, else the most recent one before it. An institution without such
    a record, and a branch without an institution, log a warning.
    """
    institutions = [
        i for i in records[Institution] if i.country_id == country.country_id
    ]
    _check_one_executive(country, institutions)
    selected = []
    for institution in institutions:
        instance = _instance(records, institution, as_of)
        if instance is None:
            logger.warning(
                f"{country.name}: '{institution.name}' has no records valid on or "
                f"before {as_of}, not imported."
            )
        else:
            branch, _ = BRANCHES[institution.branch]
            selected.append((branch, institution, instance))
    branches = {branch for branch, _, _ in selected}
    for branch in InstitutionBranch:
        if branch not in branches:
            logger.warning(
                f"{country.name}: no {branch} institution, imported without one."
            )
    return selected


def select_parties(
    records: dict[type[BaseModel], list[BaseModel]],
    country: Country,
    institutions: list[tuple[InstitutionBranch, Institution, Instance]],
    as_of: date,
) -> list[tuple[PoliticalParty, PartyPosition | None]]:
    """
    The parties of `country` that are active on the reference date (see
    `_reference_date`), each with its position on that date, if it has one.
    Skipped parties, and more parties than seats in a chamber, log a warning.
    """
    day = _reference_date(institutions, as_of)
    parties = [p for p in records[PoliticalParty] if p.country_id == country.country_id]
    active = [p for p in parties if is_valid_on(p.date_founded, p.date_dissolved, day)]
    if len(active) < len(parties):
        logger.warning(
            f"{country.name}: {len(parties) - len(active)} of {len(parties)} "
            f"parties skipped: not active on {day}."
        )
    for branch, institution, chamber in institutions:
        if branch == InstitutionBranch.LEGISLATIVE and len(active) >= chamber.size:
            logger.warning(
                f"{country.name}: {len(active)} parties for {chamber.size} seats "
                f"in '{institution.name}', the seat model gives each party only "
                "its leader."
            )
    return [(party, _position_on(records, party, day)) for party in active]


def _reference_date(
    institutions: list[tuple[InstitutionBranch, Institution, Instance]], as_of: date
) -> date:
    """
    The moment the parties are taken from, so that they come from the same
    period as the selected cabinet: the import date while that cabinet is
    valid (or without a cabinet), else the cabinet's last day.
    """
    cabinet = next(
        (r for branch, _, r in institutions if branch == InstitutionBranch.EXECUTIVE),
        None,
    )
    if cabinet is None or cabinet.valid_to is None:
        return as_of
    return min(as_of, cabinet.valid_to - timedelta(days=1))


def _check_one_executive(country: Country, institutions: list[Institution]) -> None:
    """
    The parties are taken from the period of the cabinet (see
    `_reference_date`), so a country can have only one executive institution.
    """
    names = [f"'{i.name}'" for i in institutions if i.branch == "executive"]
    if len(names) > 1:
        raise DataImportError(
            f"{country.name}: {len(names)} executive institutions "
            f"({', '.join(names)}), only one is supported."
        )


def _instance(
    records: dict[type[BaseModel], list[BaseModel]],
    institution: Institution,
    as_of: date,
) -> Instance | None:
    _, contract = BRANCHES[institution.branch]
    instances = [
        r for r in records[contract] if r.institution_id == institution.institution_id
    ]
    return current_or_latest(instances, as_of)


def _position_on(
    records: dict[type[BaseModel], list[BaseModel]], party: PoliticalParty, day: date
) -> PartyPosition | None:
    positions = [
        p
        for p in records[PartyPosition]
        if p.political_party_id == party.political_party_id
    ]
    return valid_on(positions, day)
