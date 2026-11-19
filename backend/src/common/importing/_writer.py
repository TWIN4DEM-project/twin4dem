from collections import Counter
from dataclasses import dataclass, field

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import models, transaction
from twin4dem_data_contracts.models import Cabinet

from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    InstitutionKind,
    Party,
    PartyPosition,
    UserSettings,
)

from ._errors import raise_if_any
from ._selection import CountrySelection, SelectedInstitution


@dataclass
class WriteResult:
    created: Counter[type[models.Model]] = field(default_factory=Counter)
    skipped: Counter[type[models.Model]] = field(default_factory=Counter)
    warnings: list[str] = field(default_factory=list)


def write(selections: list[CountrySelection], user: AbstractBaseUser) -> WriteResult:
    result = WriteResult()
    with transaction.atomic():
        for selection in selections:
            _write_country(selection, user, result)
    return result


def _write_country(
    selection: CountrySelection, user: AbstractBaseUser, result: WriteResult
) -> None:
    name = selection.country.name
    settings = _save(result, UserSettings, user=user, label=name)
    country = _save(result, Country, user_settings=settings, name=name)
    institutions = {
        s.branch: _write_institution(s, country, result) for s in selection.institutions
    }
    chamber = institutions.get(InstitutionBranch.LEGISLATIVE)
    if chamber is None and selection.parties:
        result.warnings.append(f"{name}: no chamber, party positions not imported.")
    for selected in selection.parties:
        party = _save(result, Party, country=country, label=selected.party.name)
        if chamber is not None:
            _save(
                result,
                PartyPosition,
                party=party,
                chamber=chamber,
                defaults={"position": selected.position.position},
            )


def _write_institution(
    selected: SelectedInstitution, country: Country, result: WriteResult
) -> Institution:
    kind = _save(
        result,
        InstitutionKind,
        country=country,
        institution_name=selected.institution.name,
        branch=selected.branch,
    )
    instance = selected.instance
    label = instance.name if isinstance(instance, Cabinet) else kind.institution_name
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
        raise_if_any([f"{model.__name__} ({where}): {m}" for m in e.messages])
    record.save()
    result.created[model] += 1
    return record
