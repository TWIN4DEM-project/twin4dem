import csv
import logging
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

logger = logging.getLogger(__name__)

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


def read_records(folder: Path) -> dict[type[BaseModel], list[BaseModel]]:
    """
    The records of the contract files of `folder`, per contract. Each file is
    parsed and its rows validated against its contract. A missing optional
    file has no records and logs a warning.

    Raises a DataImportError at the first file with a problem.
    """
    records: dict[type[BaseModel], list[BaseModel]] = {}
    for file_name, contract in CONTRACT_FILES.items():
        path = folder / file_name
        if path.is_file():
            try:
                records[contract] = _validate(_parse_csv(path), contract)
            except ValidationError as e:
                raise DataImportError(
                    *(f"{file_name} {_describe(error)}" for error in e.errors())
                )
            except UnicodeDecodeError:
                raise DataImportError(f"{file_name}: not a UTF-8 text file.")
        elif file_name in REQUIRED_FILES:
            raise DataImportError(f"{file_name}: required file is missing.")
        else:
            logger.warning(f"{file_name}: file is missing, nothing imported from it.")
            records[contract] = []
    return records


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
