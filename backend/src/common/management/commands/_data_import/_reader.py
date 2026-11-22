import csv
from collections import Counter
from functools import cache
from pathlib import Path

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

from ._exceptions import DataImportError

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


def read_records(
    folder: Path, warnings: list[str]
) -> dict[type[BaseModel], list[BaseModel]]:
    """
    The records of the contract files of `folder`, per contract. Each file is
    parsed and its rows validated against its contract, then the ids and
    references across files are checked. A missing optional file has no
    records and adds a warning to `warnings`.

    Raises a DataImportError listing every problem found.
    """
    records: dict[str, list[BaseModel]] = {}
    errors: list[str] = []
    for file_name, contract in CONTRACT_FILES.items():
        path = folder / file_name
        if path.is_file():
            try:
                records[file_name] = _validate(_parse_csv(path), contract)
            except ValidationError as e:
                errors += [f"{file_name} {_describe(error)}" for error in e.errors()]
            except UnicodeDecodeError:
                errors.append(f"{file_name}: not a UTF-8 text file.")
        elif file_name in REQUIRED_FILES:
            errors.append(f"{file_name}: required file is missing.")
        else:
            warnings.append(f"{file_name}: file is missing, nothing imported from it.")
            records[file_name] = []
    if errors:
        raise DataImportError(*errors)

    for file_name in records:
        errors += _check_keys(file_name, records)
    if errors:
        raise DataImportError(*errors)
    return {
        CONTRACT_FILES[name]: file_records for name, file_records in records.items()
    }


def _parse_csv(path: Path) -> list[dict[str, str | None]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [
            {column: cell or None for column, cell in line.items()}
            for line in csv.DictReader(stream)
        ]


def _validate[T: BaseModel](
    rows: list[dict[str, str | None]], contract: type[T]
) -> list[T]:
    return TypeAdapter(list[contract]).validate_python(rows)


def _describe(error: ErrorDetails) -> str:
    index, *field = error["loc"]
    return f"line {index + 2}: {'.'.join(map(str, field))}: {error['msg']}"


def _check_keys(file_name: str, records: dict[str, list[BaseModel]]) -> list[str]:
    key = _primary_key(file_name)
    ids = Counter(getattr(record, key) for record in records[file_name])
    errors = [
        f"{file_name}: duplicate {key} {value}."
        for value, count in ids.items()
        if count > 1
    ]
    for field_name, target in _references(file_name):
        known = {getattr(record, _primary_key(target)) for record in records[target]}
        missing = {getattr(record, field_name) for record in records[file_name]} - known
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
