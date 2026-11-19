from collections import defaultdict
from dataclasses import dataclass
from datetime import date

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

from ._errors import raise_if_any
from ._reader import Delivery

type Instance = Cabinet | Chamber | Court

BRANCHES: dict[str, tuple[InstitutionBranch, type[Instance]]] = {
    "executive": (InstitutionBranch.EXECUTIVE, Cabinet),
    "legislative": (InstitutionBranch.LEGISLATIVE, Chamber),
    "judicial": (InstitutionBranch.JUDICIARY, Court),
}


@dataclass(frozen=True)
class SelectedInstitution:
    institution: Institution
    instance: Instance

    @property
    def branch(self) -> InstitutionBranch:
        return BRANCHES[self.institution.branch][0]


@dataclass(frozen=True)
class SelectedParty:
    party: PoliticalParty
    position: PartyPosition


@dataclass(frozen=True)
class CountrySelection:
    """What to import for one country of a delivery, and what is left out."""

    country: Country
    as_of: date
    institutions: tuple[SelectedInstitution, ...]
    parties: tuple[SelectedParty, ...]
    skipped_institutions: tuple[Institution, ...]
    skipped_parties: tuple[PoliticalParty, ...]

    @property
    def chamber(self) -> SelectedInstitution | None:
        return next(
            (s for s in self.institutions if s.branch == InstitutionBranch.LEGISLATIVE),
            None,
        )

    @property
    def warnings(self) -> tuple[str, ...]:
        name, as_of = self.country.name, self.as_of
        warnings = [
            f"{name}: '{i.name}' has no records valid on or before {as_of}, "
            "not imported."
            for i in self.skipped_institutions
        ]
        branches = {s.branch for s in self.institutions}
        warnings += [
            f"{name}: no {branch} institution, imported without one."
            for branch in InstitutionBranch
            if branch not in branches
        ]
        if self.skipped_parties:
            total = len(self.parties) + len(self.skipped_parties)
            warnings.append(
                f"{name}: {len(self.skipped_parties)} of {total} parties skipped: "
                f"no position on or before {as_of}, or not active on that date."
            )
        if self.chamber and len(self.parties) >= self.chamber.instance.size:
            warnings.append(
                f"{name}: {len(self.parties)} parties for "
                f"{self.chamber.instance.size} seats in "
                f"'{self.chamber.institution.name}', the seat model gives each "
                "party only its leader."
            )
        return tuple(warnings)


def select(delivery: Delivery, as_of: date) -> list[CountrySelection]:
    """What to import from `delivery` for each of its countries, as of `as_of`."""
    return [
        _select_country(delivery, country, as_of) for country in delivery.of(Country)
    ]


def is_valid_on(valid_from: date | None, valid_to: date | None, day: date) -> bool:
    """
    Whether `day` is in the window [valid_from, valid_to): the end day is
    excluded, and None leaves that side open.
    """
    return (valid_from is None or valid_from <= day) and (
        valid_to is None or day < valid_to
    )


def current_or_latest[T: Instance | PartyPosition](
    records: list[T], as_of: date, label: str
) -> T | None:
    """
    The record valid on `as_of`, else the most recent one before it. Records
    starting after `as_of` are ignored.
    """
    valid = [r for r in records if is_valid_on(r.valid_from, r.valid_to, as_of)]
    if len(valid) > 1:
        raise_if_any(
            [f"{label}: {len(valid)} records are valid on {as_of}, overlapping."]
        )
    started = [r for r in records if is_valid_on(r.valid_from, None, as_of)]
    return max(started, key=lambda r: r.valid_from or date.min, default=None)


def is_importable_party(
    party: PoliticalParty, position: PartyPosition | None, as_of: date
) -> bool:
    return position is not None and is_valid_on(
        party.date_founded, party.date_dissolved, as_of
    )


def _select_country(
    delivery: Delivery, country: Country, as_of: date
) -> CountrySelection:
    institutions = [
        i for i in delivery.of(Institution) if i.country_id == country.country_id
    ]
    _check_one_per_branch(country, institutions)
    instances = [(i, _instance(delivery, i, as_of)) for i in institutions]
    parties = [
        p for p in delivery.of(PoliticalParty) if p.country_id == country.country_id
    ]
    positions = [(p, _latest_position(delivery, p, as_of)) for p in parties]
    return CountrySelection(
        country=country,
        as_of=as_of,
        institutions=tuple(
            SelectedInstitution(i, inst) for i, inst in instances if inst
        ),
        parties=tuple(
            SelectedParty(p, pos)
            for p, pos in positions
            if is_importable_party(p, pos, as_of)
        ),
        skipped_institutions=tuple(i for i, inst in instances if not inst),
        skipped_parties=tuple(
            p for p, pos in positions if not is_importable_party(p, pos, as_of)
        ),
    )


def _check_one_per_branch(country: Country, institutions: list[Institution]) -> None:
    names = defaultdict(list)
    for institution in institutions:
        names[institution.branch].append(f"'{institution.name}'")
    raise_if_any(
        [
            f"{country.name}: {len(group)} {branch} institutions "
            f"({', '.join(group)}), only one per branch is supported."
            for branch, group in names.items()
            if len(group) > 1
        ]
    )


def _instance(
    delivery: Delivery, institution: Institution, as_of: date
) -> Instance | None:
    _, contract = BRANCHES[institution.branch]
    records = [
        r
        for r in delivery.of(contract)
        if r.institution_id == institution.institution_id
    ]
    return current_or_latest(records, as_of, f"'{institution.name}'")


def _latest_position(
    delivery: Delivery, party: PoliticalParty, as_of: date
) -> PartyPosition | None:
    positions = [
        p
        for p in delivery.of(PartyPosition)
        if p.political_party_id == party.political_party_id
    ]
    return current_or_latest(positions, as_of, f"positions of '{party.name}'")
