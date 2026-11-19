from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

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
    reference_date: date
    institutions: tuple[SelectedInstitution, ...]
    parties: tuple[SelectedParty, ...]
    skipped_institutions: tuple[Institution, ...]
    skipped_parties: tuple[PoliticalParty, ...]

    @property
    def chamber(self) -> SelectedInstitution | None:
        return _of_branch(self.institutions, InstitutionBranch.LEGISLATIVE)

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
                f"no position on {self.reference_date}, or not active on that date."
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


def valid_on[T: Instance | PartyPosition](
    records: list[T], day: date, label: str
) -> T | None:
    """The record valid on `day`, if any. Overlapping records are an error."""
    valid = [r for r in records if is_valid_on(r.valid_from, r.valid_to, day)]
    if len(valid) > 1:
        raise_if_any(
            [f"{label}: {len(valid)} records are valid on {day}, overlapping."]
        )
    return valid[0] if valid else None


def current_or_latest[T: Instance | PartyPosition](
    records: list[T], as_of: date, label: str
) -> T | None:
    """
    The record valid on `as_of`, else the most recent one before it. Records
    starting after `as_of` are ignored.
    """
    current = valid_on(records, as_of, label)
    if current is not None:
        return current
    started = [r for r in records if is_valid_on(r.valid_from, None, as_of)]
    return max(started, key=lambda r: r.valid_from or date.min, default=None)


def is_importable_party(
    party: PoliticalParty, position: PartyPosition | None, day: date
) -> bool:
    return position is not None and is_valid_on(
        party.date_founded, party.date_dissolved, day
    )


def _select_country(
    delivery: Delivery, country: Country, as_of: date
) -> CountrySelection:
    institutions = [
        i for i in delivery.of(Institution) if i.country_id == country.country_id
    ]
    _check_one_per_branch(country, institutions)
    instances = [(i, _instance(delivery, i, as_of)) for i in institutions]
    selected = tuple(SelectedInstitution(i, inst) for i, inst in instances if inst)
    day = _reference_date(selected, as_of)
    parties = [
        p for p in delivery.of(PoliticalParty) if p.country_id == country.country_id
    ]
    positions = [(p, _position_on(delivery, p, day)) for p in parties]
    return CountrySelection(
        country=country,
        as_of=as_of,
        reference_date=day,
        institutions=selected,
        parties=tuple(
            SelectedParty(p, pos)
            for p, pos in positions
            if is_importable_party(p, pos, day)
        ),
        skipped_institutions=tuple(i for i, inst in instances if not inst),
        skipped_parties=tuple(
            p for p, pos in positions if not is_importable_party(p, pos, day)
        ),
    )


def _reference_date(institutions: tuple[SelectedInstitution, ...], as_of: date) -> date:
    """
    The moment the parties are taken from, so that they come from the same
    period as the selected cabinet: the import date while that cabinet is
    valid (or without a cabinet), else the cabinet's last day.
    """
    cabinet = _of_branch(institutions, InstitutionBranch.EXECUTIVE)
    if cabinet is None or cabinet.instance.valid_to is None:
        return as_of
    return min(as_of, cabinet.instance.valid_to - timedelta(days=1))


def _of_branch(
    institutions: tuple[SelectedInstitution, ...], branch: InstitutionBranch
) -> SelectedInstitution | None:
    return next((s for s in institutions if s.branch == branch), None)


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


def _position_on(
    delivery: Delivery, party: PoliticalParty, day: date
) -> PartyPosition | None:
    positions = [
        p
        for p in delivery.of(PartyPosition)
        if p.political_party_id == party.political_party_id
    ]
    return valid_on(positions, day, f"positions of '{party.name}'")
