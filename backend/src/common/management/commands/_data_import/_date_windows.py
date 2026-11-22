from datetime import date

from twin4dem_data_contracts.models import Cabinet, Chamber, Court, PartyPosition

from ._exceptions import DataImportError

type TimeBound = Cabinet | Chamber | Court | PartyPosition


def is_valid_on(valid_from: date | None, valid_to: date | None, day: date) -> bool:
    """
    Whether `day` is in the window [valid_from, valid_to): the end day is
    excluded, and None leaves that side open.
    """
    return (valid_from is None or valid_from <= day) and (
        valid_to is None or day < valid_to
    )


def valid_on[T: TimeBound](records: list[T], day: date, label: str) -> T | None:
    """The record valid on `day`, if any. Overlapping records are an error."""
    valid = [r for r in records if is_valid_on(r.valid_from, r.valid_to, day)]
    if len(valid) > 1:
        raise DataImportError(
            f"{label}: {len(valid)} records are valid on {day}, overlapping."
        )
    return valid[0] if valid else None


def current_or_latest[T: TimeBound](
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
