import csv
import io
from collections import Counter
from dataclasses import dataclass
from functools import cache

from django.core.files.storage import Storage
from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_core import ErrorDetails
from twin4dem_data_contracts.models import (
    Cabinet,
    Chamber,
    Country,
    Court,
    Institution,
    PartyPosition,
    PoliticalParty,
)

from ._errors import raise_if_any

CONTRACT_FILES: dict[str, type[BaseModel]] = {
    "country.csv": Country,
    "institution.csv": Institution,
    "cabinet.csv": Cabinet,
    "chamber.csv": Chamber,
    "court.csv": Court,
    "political-party.csv": PoliticalParty,
    "party-position.csv": PartyPosition,
}
REQUIRED_FILES = frozenset({"country.csv", "institution.csv"})


@dataclass(frozen=True)
class Delivery:
    records: dict[type[BaseModel], list[BaseModel]]
    warnings: tuple[str, ...] = ()

    def of[T: BaseModel](self, contract: type[T]) -> list[T]:
        return self.records.get(contract, [])


def read_delivery(storage: Storage) -> Delivery:
    """
    Read the contract files of `storage` and check them: each row against its
    contract, then unique ids and references across files.

    Raises a DataImportError listing every problem found.
    """
    rows: dict[str, list[BaseModel]] = {}
    warnings: list[str] = []
    errors: list[str] = []
    for file_name in CONTRACT_FILES:
        if storage.exists(file_name):
            try:
                rows[file_name] = _read_file(storage, file_name)
            except ValidationError as e:
                errors += [f"{file_name} {_describe(error)}" for error in e.errors()]
            except UnicodeDecodeError:
                errors.append(f"{file_name}: not a UTF-8 text file.")
        elif file_name in REQUIRED_FILES:
            errors.append(f"{file_name}: required file is missing.")
        else:
            warnings.append(f"{file_name}: file is missing, nothing imported from it.")
    raise_if_any(errors)

    for file_name in rows:
        errors += _check_keys(file_name, rows)
    raise_if_any(errors)
    return Delivery(
        {CONTRACT_FILES[name]: file_rows for name, file_rows in rows.items()},
        tuple(warnings),
    )


def _read_file(storage: Storage, file_name: str) -> list[BaseModel]:
    with storage.open(file_name, "rb") as stream:
        lines = csv.DictReader(
            io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
        )
        rows = [{key: value or None for key, value in line.items()} for line in lines]
    return TypeAdapter(list[CONTRACT_FILES[file_name]]).validate_python(rows)


def _describe(error: ErrorDetails) -> str:
    index, *field = error["loc"]
    return f"line {index + 2}: {'.'.join(map(str, field))}: {error['msg']}"


def _check_keys(file_name: str, rows: dict[str, list[BaseModel]]) -> list[str]:
    key = _primary_key(file_name)
    ids = Counter(getattr(row, key) for row in rows[file_name])
    errors = [
        f"{file_name}: duplicate {key} {value}."
        for value, count in ids.items()
        if count > 1
    ]
    for field_name, target in _references(file_name):
        known = {getattr(row, _primary_key(target)) for row in rows.get(target, [])}
        missing = {getattr(row, field_name) for row in rows[file_name]} - known
        errors += [
            f"{file_name}: {field_name} {value} not found in {target}."
            for value in sorted(missing, key=str)
        ]
    return errors


@cache
def _primary_key(file_name: str) -> str:
    return next(
        name
        for name, info in CONTRACT_FILES[file_name].model_fields.items()
        if isinstance(info.json_schema_extra, dict)
        and info.json_schema_extra.get("primaryKey")
    )


@cache
def _references(file_name: str) -> list[tuple[str, str]]:
    by_key = {
        _primary_key(other): other for other in CONTRACT_FILES if other != file_name
    }
    fields = CONTRACT_FILES[file_name].model_fields
    return [(name, by_key[name]) for name in fields if name in by_key]
