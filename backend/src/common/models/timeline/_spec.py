from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FrameSpec:
    """An interval ``[valid_from, valid_to)`` on a set of timelines.

    A missing bound signifies that that end is open. When ``timeline_ids=None``
    it means that the time frame is registered on all timelines.
    """

    valid_from: datetime | None
    valid_to: datetime | None
    timeline_ids: frozenset[int] | None

    def overlaps_in_time(self, other: "FrameSpec") -> bool:
        starts_before_other_ends = (
            self.valid_from is None
            or other.valid_to is None
            or self.valid_from < other.valid_to
        )
        other_starts_before_end = (
            other.valid_from is None
            or self.valid_to is None
            or other.valid_from < self.valid_to
        )
        return starts_before_other_ends and other_starts_before_end

    def shared_timelines(self, other: "FrameSpec") -> frozenset[int] | None:
        """The timelines both frames are on (None: all timelines)."""
        if self.timeline_ids is None:
            return other.timeline_ids
        if other.timeline_ids is None:
            return self.timeline_ids
        return self.timeline_ids & other.timeline_ids

    def shares_timeline_with(self, other: "FrameSpec") -> bool:
        shared = self.shared_timelines(other)
        return shared is None or bool(shared)

    def contains(self, timeline_id: int, at: datetime) -> bool:
        """Whether the frame covers the point in time `at` on the timeline."""
        on_timeline = self.timeline_ids is None or timeline_id in self.timeline_ids
        started = self.valid_from is None or self.valid_from <= at
        not_ended = self.valid_to is None or at < self.valid_to
        return on_timeline and started and not_ended


# a subject without time frames is active at all times, on all timelines
ALWAYS = FrameSpec(valid_from=None, valid_to=None, timeline_ids=None)


def _format_bound(value: datetime | None, default: str) -> str:
    if value is None:
        return default
    is_midnight = (value.hour, value.minute, value.second, value.microsecond) == (
        0,
        0,
        0,
        0,
    )
    return value.date().isoformat() if is_midnight else value.isoformat()


def _format_interval(spec: FrameSpec) -> str:
    start = _format_bound(spec.valid_from, "-inf")
    end = _format_bound(spec.valid_to, "+inf")
    return f"[{start}, {end})"


def _format_timelines(timeline_ids: frozenset[int] | None, labels: dict) -> str:
    if timeline_ids is None:
        return "all timelines"
    names = sorted(f"'{labels.get(i, i)}'" for i in timeline_ids)
    return ("timeline " if len(names) == 1 else "timelines ") + ", ".join(names)
