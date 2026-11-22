from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import models
from twin4dem_data_contracts import models as contracts

from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    InstitutionKind,
    Party,
    PartyPosition,
    UserSettings,
)

from ._exceptions import DataImportError
from ._selection import Instance


def write_country(
    user: AbstractBaseUser,
    country: contracts.Country,
    institutions: dict[InstitutionBranch, tuple[contracts.Institution, Instance]],
    parties: list[tuple[contracts.PoliticalParty, contracts.PartyPosition]],
    warnings: list[str],
) -> None:
    settings = _find_or_create_settings(user, country.name)
    saved_country = _find_or_create_country(settings, country.name)
    chamber = None
    for branch, (institution, instance) in institutions.items():
        kind = _find_or_create_kind(saved_country, institution.name, branch)
        if isinstance(instance, contracts.Cabinet):
            label = instance.name
        else:
            label = institution.name
        saved_institution = _find_or_create_institution(kind, label, instance.size)
        if branch == InstitutionBranch.LEGISLATIVE:
            chamber = saved_institution
    if chamber is None and parties:
        warnings.append(f"{country.name}: no chamber, party positions not imported.")
    for party, position in parties:
        saved_party = _find_or_create_party(saved_country, party.name)
        if chamber is not None:
            _find_or_create_position(saved_party, chamber, position.position)


def _find_or_create_settings(user: AbstractBaseUser, label: str) -> UserSettings:
    found = UserSettings.objects.filter(user=user, label=label).first()
    return found or _create(UserSettings(user=user, label=label), f"settings '{label}'")


def _find_or_create_country(settings: UserSettings, name: str) -> Country:
    found = Country.objects.filter(user_settings=settings, name=name).first()
    return found or _create(
        Country(user_settings=settings, name=name), f"country '{name}'"
    )


def _find_or_create_kind(
    country: Country, name: str, branch: InstitutionBranch
) -> InstitutionKind:
    found = InstitutionKind.objects.filter(
        country=country, institution_name=name, branch=branch
    ).first()
    return found or _create(
        InstitutionKind(country=country, institution_name=name, branch=branch),
        f"{branch} institution '{name}' of {country}",
    )


def _find_or_create_institution(
    kind: InstitutionKind, label: str, size: int
) -> Institution:
    found = Institution.objects.filter(kind=kind).first()
    return found or _create(
        Institution(kind=kind, label=label, size=size),
        f"institution '{label}' of {kind.country}",
    )


def _find_or_create_party(country: Country, label: str) -> Party:
    found = Party.objects.filter(country=country, label=label).first()
    return found or _create(
        Party(country=country, label=label), f"party '{label}' of {country}"
    )


def _find_or_create_position(
    party: Party, chamber: Institution, position: str
) -> PartyPosition:
    found = PartyPosition.objects.filter(party=party, chamber=chamber).first()
    return found or _create(
        PartyPosition(party=party, chamber=chamber, position=position),
        f"position of party '{party}' in '{chamber.label}'",
    )


def _create[M: models.Model](record: M, description: str) -> M:
    try:
        record.full_clean()
    except ValidationError as e:
        raise DataImportError(*(f"{description}: {m}" for m in e.messages))
    record.save()
    return record
