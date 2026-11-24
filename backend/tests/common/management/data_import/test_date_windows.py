from datetime import date
from uuid import uuid4

import pytest
from twin4dem_data_contracts.models import PartyPosition

from common.management.commands._data_import._date_windows import (
    current_or_latest,
    is_valid_on,
    valid_on,
)

START = date(2020, 1, 1)
END = date(2021, 1, 1)


def record(valid_from: date | None, valid_to: date | None) -> PartyPosition:
    """A contract record valid from `valid_from` until `valid_to`."""
    return PartyPosition(
        party_position_id=uuid4(),
        political_party_id=uuid4(),
        position="majority",
        valid_from=valid_from,
        valid_to=valid_to,
        source_system="test",
        record_updated_at="2026-01-01T00:00:00Z",
    )


@pytest.mark.parametrize(
    "day,valid",
    [
        (date(2019, 12, 31), False),
        (START, True),  # the start day is included
        (date(2020, 12, 31), True),
        (END, False),  # the end day is excluded
    ],
)
def test_window_includes_its_start_day_and_excludes_its_end_day(day, valid):
    assert is_valid_on(START, END, day) is valid


def test_window_without_start_is_open_to_the_past():
    assert is_valid_on(None, END, date.min)


def test_window_without_end_is_open_to_the_future():
    assert is_valid_on(START, None, date.max)


def test_valid_on_finds_the_record_whose_window_has_the_day():
    first, second = record(START, END), record(END, None)

    assert valid_on([first, second], END) is second


def test_valid_on_finds_nothing_when_no_window_has_the_day():
    assert valid_on([record(START, END)], END) is None


def test_current_or_latest_takes_the_record_valid_on_the_date():
    current = record(START, None)
    records = [record(None, START), current]

    assert current_or_latest(records, END) is current


def test_current_or_latest_else_takes_the_latest_started_before_the_date():
    older, latest = record(date(2010, 1, 1), date(2015, 1, 1)), record(START, END)

    assert current_or_latest([latest, older], date(2025, 1, 1)) is latest


def test_current_or_latest_ignores_records_starting_after_the_date():
    assert current_or_latest([record(END, None)], START) is None


def test_record_without_start_counts_as_started():
    ended = record(None, START)

    assert current_or_latest([ended], END) is ended
