from typing import ClassVar
from ._timeline import VirtualTimeline


class TimelineMap[V](dict[int | None, V]):
    """Values grouped by timeline id.

    Handles the ceremony around extracting the primary key of the timeline.
    """

    ALL_TIMELINES: ClassVar[None] = None

    @property
    def all_timelines(self) -> V | None:
        """Values that are associated with all timelines."""
        return self.get(self.ALL_TIMELINES)

    def for_timeline(self, timeline: VirtualTimeline | int) -> V | None:
        """Values associated with the given timeline.

        :raises TypeError: if the timeline parameter is not of the correct type.
        """
        """The timeline's own value, falling back to the all-timelines value."""
        key = self._check_timeline_value(timeline)
        return super().__getitem__(key)

    def __getitem__(self, key: int | VirtualTimeline | None, /) -> V:
        if key is None:
            return self.all_timelines
        else:
            return self.for_timeline(key)

    def __setitem__(self, key: int | VirtualTimeline | None, value: V, /) -> None:
        if key is None:
            super().__setitem__(self.ALL_TIMELINES, value)
        else:
            super().__setitem__(self._check_timeline_value(key), value)

    @staticmethod
    def _check_timeline_value(timeline: VirtualTimeline | int) -> int:
        match timeline:
            case VirtualTimeline() | int():
                key = timeline.pk if isinstance(timeline, VirtualTimeline) else timeline
            case _:
                raise TypeError(
                    f"unsupported timeline type: '{type(timeline).__name__}'"
                )
        return key
