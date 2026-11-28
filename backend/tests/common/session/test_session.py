import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore

from common.models import UserSettings
from common.session import current_settings, set_current_settings


def session_request(rf, user):
    request = rf.get("/admin/")
    request.user = user
    request.session = SessionStore()
    return request


@pytest.mark.django_db
def test_current_settings_defaults_to_the_users_default_settings(
    rf, staff_user, staff_settings
):
    assert current_settings(session_request(rf, staff_user)) == staff_settings


@pytest.mark.django_db
def test_current_settings_returns_the_selected_settings(rf, staff_user):
    selected = UserSettings.objects.create(user=staff_user, label="second")
    request = session_request(rf, staff_user)
    set_current_settings(request, selected)

    assert current_settings(request) == selected


@pytest.mark.django_db
def test_current_settings_ignores_selections_of_other_users(
    rf, staff_user, staff_settings, test_settings
):
    request = session_request(rf, staff_user)
    set_current_settings(request, test_settings)

    assert current_settings(request) == staff_settings


@pytest.mark.django_db
def test_current_settings_allows_superusers_to_select_other_users_settings(
    rf, admin_user, staff_settings
):
    request = session_request(rf, admin_user)
    set_current_settings(request, staff_settings)

    assert current_settings(request) == staff_settings


@pytest.mark.django_db
def test_current_settings_is_none_for_anonymous_requests(rf):
    assert current_settings(session_request(rf, AnonymousUser())) is None
