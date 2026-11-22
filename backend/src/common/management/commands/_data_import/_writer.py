from collections import Counter
from dataclasses import dataclass, field

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


@dataclass
class WriteResult:
    created: Counter[type[models.Model]] = field(default_factory=Counter)
    skipped: Counter[type[models.Model]] = field(default_factory=Counter)


def write_country(
    user: AbstractBaseUser,
    country: contracts.Country,
    institutions: dict[InstitutionBranch, tuple[contracts.Institution, Instance]],
    parties: list[tuple[contracts.PoliticalParty, contracts.PartyPosition]],
    result: WriteResult,
    warnings: list[str],
) -> None:
    settings = _save(result, UserSettings, user=user, label=country.name)
    saved_country = _save(result, Country, user_settings=settings, name=country.name)
    saved = {
        branch: _write_institution(branch, institution, instance, saved_country, result)
        for branch, (institution, instance) in institutions.items()
    }
    chamber = saved.get(InstitutionBranch.LEGISLATIVE)
    if chamber is None and parties:
        warnings.append(f"{country.name}: no chamber, party positions not imported.")
    for party, position in parties:
        saved_party = _save(result, Party, country=saved_country, label=party.name)
        if chamber is not None:
            _save(
                result,
                PartyPosition,
                party=saved_party,
                chamber=chamber,
                defaults={"position": position.position},
            )


def _write_institution(
    branch: InstitutionBranch,
    institution: contracts.Institution,
    instance: Instance,
    country: Country,
    result: WriteResult,
) -> Institution:
    kind = _save(
        result,
        InstitutionKind,
        country=country,
        institution_name=institution.name,
        branch=branch,
    )
    if isinstance(instance, contracts.Cabinet):
        label = instance.name
    else:
        label = kind.institution_name
    return _save(
        result, Institution, kind=kind, defaults={"label": label, "size": instance.size}
    )


def _save[M: models.Model](
    result: WriteResult, model: type[M], defaults: dict | None = None, **lookup
) -> M:
    record = model.objects.filter(**lookup).first()
    if record is not None:
        result.skipped[model] += 1
        return record
    record = model(**lookup, **(defaults or {}))
    try:
        record.full_clean()
    except ValidationError as e:
        where = ", ".join(f"{key}={value}" for key, value in lookup.items())
        raise DataImportError(*(f"{model.__name__} ({where}): {m}" for m in e.messages))
    record.save()
    result.created[model] += 1
    return record
