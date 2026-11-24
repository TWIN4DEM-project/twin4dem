import logging
from datetime import date

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

logger = logging.getLogger(__name__)

type Instance = Cabinet | Chamber | Court

BRANCHES: dict[str, tuple[InstitutionBranch, type[Instance]]] = {
    "executive": (InstitutionBranch.EXECUTIVE, Cabinet),
    "legislative": (InstitutionBranch.LEGISLATIVE, Chamber),
    "judicial": (InstitutionBranch.JUDICIARY, Court),
}


def select_institutions(
    records: dict[type[BaseModel], list[BaseModel]], country: Country
) -> list[tuple[InstitutionBranch, Institution, Instance]]:
    """
    The institutions of `country`, each with its branch and its most recent
    record. An institution without records, and a branch without an
    institution, log a warning.
    """
    selected = []
    for institution in records[Institution]:
        if institution.country_id != country.country_id:
            continue
        branch, contract = BRANCHES[institution.branch]
        instances = [
            r
            for r in records[contract]
            if r.institution_id == institution.institution_id
        ]
        instance = _latest(instances)
        if instance is None:
            logger.warning(
                f"{country.name}: '{institution.name}' has no records, not imported."
            )
        else:
            selected.append((branch, institution, instance))
    branches = {branch for branch, _, _ in selected}
    for branch in InstitutionBranch:
        if branch not in branches:
            logger.warning(
                f"{country.name}: no {branch} institution, imported without one."
            )
    return selected


def select_parties(
    records: dict[type[BaseModel], list[BaseModel]], country: Country
) -> list[tuple[PoliticalParty, PartyPosition | None]]:
    """
    The parties of `country` that are not dissolved, each with its most recent
    position, if it has one.
    """
    selected = []
    for party in records[PoliticalParty]:
        if party.country_id != country.country_id or party.date_dissolved is not None:
            continue
        positions = [
            p
            for p in records[PartyPosition]
            if p.political_party_id == party.political_party_id
        ]
        selected.append((party, _latest(positions)))
    return selected


def _latest[T: Instance | PartyPosition](records: list[T]) -> T | None:
    """
    The record that ends last. A record without an end date is still active,
    so it is the latest.
    """
    return max(records, key=lambda r: r.valid_to or date.max, default=None)
