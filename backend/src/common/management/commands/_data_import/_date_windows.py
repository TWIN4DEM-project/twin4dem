from datetime import date

from twin4dem_data_contracts.models import Cabinet, Chamber, Court, PartyPosition

type TimeBound = Cabinet | Chamber | Court | PartyPosition


def is_valid_on(valid_from: date | None, valid_to: date | None, day: date) -> bool:
    """
    Whether `day` is in the window [valid_from, valid_to): the end day is
    excluded, and None leaves that side open.
    """
    return (valid_from is None or valid_from <= day) and (
        valid_to is None or day < valid_to
    )


def valid_on[T: TimeBound](records: list[T], day: date) -> T | None:
    """
    The record valid on `day`, if any. The data contracts rule out records
    that overlap, so there is at most one.
    """
    return next(
        (r for r in records if is_valid_on(r.valid_from, r.valid_to, day)), None
    )


def current_or_latest[T: TimeBound](records: list[T], as_of: date) -> T | None:
    """
    The record valid on `as_of`, else the most recent one before it. Records
    starting after `as_of` are ignored.
    """
    current = valid_on(records, as_of)
    if current is not None:
        return current
    started = [r for r in records if is_valid_on(r.valid_from, None, as_of)]
    return max(started, key=lambda r: r.valid_from or date.min, default=None)
