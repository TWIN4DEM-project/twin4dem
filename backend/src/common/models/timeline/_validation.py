from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from typing import TypeVar

from django.core.exceptions import ValidationError

from ._spec import ALWAYS, FrameSpec, _format_interval, _format_timelines
from ._subjects import TimeFrameMixin, subject_type_of
from ._timeframe import TimeFrame
from ._timeline import VirtualTimeline


T = TypeVar("T", bound=TimeFrameMixin)


def frameless_sibling(subject: T) -> T | None:
    """
    A sibling without time frames, which is active at all times on all timelines
    and therefore leaves no room for `subject`.
    """
    siblings = subject.time_frame_siblings()
    with_frames = TimeFrame.objects.filter(
        subject_type=subject_type_of(subject), subject_id__in=siblings.values("pk")
    ).values("subject_id")
    return siblings.exclude(pk__in=with_frames).first()


def validate_time_frame(
    subject: T, frame: TimeFrame, timeline_ids: Iterable[int] | None
) -> None:
    """Validate the time frame of a single subject model on the given timelines.

    1. a subject occupies at most one time frame per timeline;
    2. its siblings (see `TimeFramed.time_frame_siblings`) are not active at the
       same time on the same timeline. A sibling without time frames is always
       active.
    """
    frame_timelines = None
    if timeline_ids is not None:
        frame_timelines = frozenset(timeline_ids)
    candidate = FrameSpec(frame.valid_from, frame.valid_to, frame_timelines)

    labels = dict(
        VirtualTimeline.objects.filter(
            user_settings_id=subject.time_frame_user_settings_id()
        ).values_list("id", "label")
    )

    if (
        candidate.timeline_ids is not None
        and not candidate.timeline_ids <= labels.keys()
    ):
        raise ValidationError(
            "The timelines must belong to the same global context as the "
            "time frame's subject."
        )

    errors = []

    own_frames = TimeFrame.objects.of(subject).prefetch_related("timeline_links")
    if frame.pk is not None:
        own_frames = own_frames.exclude(pk=frame.pk)
    for other in own_frames:
        if candidate.shares_timeline_with(other.spec):
            errors.append(
                f"{subject.time_frame_label()} already occupies the time frame "
                f"{_format_interval(other.spec)} on "
                f"{_format_timelines(candidate.shared_timelines(other.spec), labels)}."
            )

    siblings = list(subject.time_frame_siblings())
    sibling_frames = defaultdict(list)
    for sibling_frame in TimeFrame.objects.filter(
        subject_type=subject_type_of(subject),
        subject_id__in=[s.pk for s in siblings],
    ).prefetch_related("timeline_links"):
        sibling_frames[sibling_frame.subject_id].append(sibling_frame.spec)

    for sibling in siblings:
        for spec in sibling_frames.get(sibling.pk) or [ALWAYS]:
            if not (
                candidate.shares_timeline_with(spec)
                and candidate.overlaps_in_time(spec)
            ):
                continue
            if spec is ALWAYS:
                errors.append(
                    f"{sibling.time_frame_label()} has no time frame, so it is "
                    f"active at all times on all timelines."
                )
            else:
                errors.append(
                    f"Overlaps with {sibling.time_frame_label()} "
                    f"{_format_interval(spec)} on "
                    f"{_format_timelines(candidate.shared_timelines(spec), labels)}."
                )

    if errors:
        raise ValidationError(errors)


def active_subjects(
    subjects: Iterable[T], timeline: VirtualTimeline, at: datetime
) -> list[T]:
    """Fetch the active subject models on a timeline at a given time.

    All subject models must be of the same type.
    A subject without time frames is always active.

    :param subjects: input subject models to filter
    :param timeline: the timeline on which the models must be active
    :param at: the time at which the models should be active

    :return: the active subject models on the specified timeline at the given time
    """
    subjects = list(subjects)
    if not subjects:
        return []
    frames = defaultdict(list)
    for frame in TimeFrame.objects.filter(
        subject_type=subject_type_of(subjects[0]),
        subject_id__in=[s.pk for s in subjects],
    ).prefetch_related("timeline_links"):
        frames[frame.subject_id].append(frame.spec)
    return [
        subject
        for subject in subjects
        if not frames[subject.pk]
        or any(spec.contains(timeline.pk, at) for spec in frames[subject.pk])
    ]


def is_active(subject: T, timeline: VirtualTimeline, at: datetime) -> bool:
    return bool(active_subjects([subject], timeline, at))
