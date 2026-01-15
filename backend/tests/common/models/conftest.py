import pytest

from common.models import UserSettings


@pytest.fixture
def test_settings(admin_user):
    return UserSettings.objects.get(user=admin_user)
