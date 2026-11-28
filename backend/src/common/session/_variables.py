from django.db import models
from django.http import HttpRequest

from common.models import UserSettings

SELECTED_SETTINGS_KEY = "current_user_settings_id"


def current_settings(request: HttpRequest) -> UserSettings | None:
    """Resolve the global user settings context.

    A selection stored in the session wins, but only if it still exists
    and, for non-superusers, still belongs to the requesting user: sessions
    outlive permission and role changes, so a stored id is not trusted by
    itself. Without a usable selection the requesting user's own default
    context applies, which keeps callers free of a missing-context case.

    :param request: The request whose session holds the selection and whose
        user owns the candidate settings contexts.
    :returns: The 'selected' ``UserSettings`` instance. If not set, returns
        the user's default context. It returns ``None`` for anonymous requests.
    """
    if not request.user.is_authenticated:
        return None
    related_settings = request.user.user_settings.all()
    candidates = (
        UserSettings.objects.all() if request.user.is_superuser else related_settings
    )
    selected = candidates.filter(pk=request.session.get(SELECTED_SETTINGS_KEY)).first()
    return selected or _default_settings(related_settings)


def _default_settings(candidates: models.QuerySet[UserSettings]) -> UserSettings | None:
    return (
        candidates.filter(label=UserSettings.DEFAULT_LABEL).first()
        or candidates.order_by("pk").first()
    )


def set_current_settings(request: HttpRequest, user_settings: UserSettings) -> None:
    """Store the ID of the user settings the admin website should work on.

    :param request: The request whose session stores the selection.
    :param user_settings: The context to remember for later requests.
    """
    request.session[SELECTED_SETTINGS_KEY] = user_settings.pk
