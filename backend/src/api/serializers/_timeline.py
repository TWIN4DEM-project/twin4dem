"""Validation of time frame timelines against the active user settings.

These helpers let serializers enforce that write operations can only link
timelines of the user settings that are active on the current request.
"""

from rest_framework import serializers

_TIMELINE_IDS_ATTR = "_current_settings_timeline_ids"

INVALID_TIMELINE_MESSAGE = (
    "The timelines must belong to the currently active user settings."
)


def current_settings_timeline_ids(request) -> frozenset[int]:
    """Resolve the timeline ids of the active user settings.

    The result is cached on the underlying HTTP request so that nested
    serializers and batch items do not incur more database lookups. Accessing
    the settings is intentionally unguarded: missing user settings are an error,
    not an empty selection.

    :param request: The DRF request with the associated user settings that
        provide the valid timelines. Must have been populated by
        ``common.middleware.CurrentSettingsMiddleware``.
    :returns: The timeline ids, as an immutable membership set.
    """
    http_request = getattr(request, "_request", request)
    cached = getattr(http_request, _TIMELINE_IDS_ATTR, None)
    if cached is not None:
        return cached
    settings = request.current_settings
    timeline_ids = frozenset(settings.timelines.values_list("id", flat=True))
    setattr(http_request, _TIMELINE_IDS_ATTR, timeline_ids)
    return timeline_ids


def validate_current_settings_timeline(request, timelines) -> None:
    """Reject timelines outside the active user settings.

    An empty selection passes: a time frame without timeline links applies to
    all timelines, and the model-level overlap checks cover it.

    :param request: The DRF request whose active user settings provide the
        allowed timelines.
    :param timelines: The selected timeline instances or ids.
    :raises rest_framework.exceptions.ValidationError: If any selected
        timeline is not part of the active settings.
    """
    timeline_ids = {getattr(timeline, "pk", timeline) for timeline in timelines or ()}
    if not timeline_ids <= current_settings_timeline_ids(request):
        raise serializers.ValidationError(INVALID_TIMELINE_MESSAGE)
