import pytest

from common.models import UserSettings


@pytest.fixture
def test_user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="testuser", password="testpass"
    )


@pytest.fixture
def test_settings(test_user):
    return UserSettings.objects.get(user_id=test_user.id)
