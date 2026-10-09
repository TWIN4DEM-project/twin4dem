import pytest
from django.db import IntegrityError, transaction

from common.models import UserSettings


@pytest.fixture
def test_user(django_user_model):
    return django_user_model.objects.get(username="test_user")


@pytest.mark.django_db
def test_create_default_user_settings(test_user):
    settings = UserSettings.objects.get(user=test_user)

    assert settings is not None
    assert settings.id > 0
    assert settings.user.username == test_user.username
    assert settings.label == "default"
    assert settings.abstention_threshold == 0.2
    assert settings.data_update_frequency == 10
    assert settings.legislative_path_probability == 0.5


@pytest.mark.django_db
@pytest.mark.parametrize(
    "property_name,check_name",
    [
        ("abstention_threshold", "ck_usersettings_abstention_threshold"),
        (
            "legislative_path_probability",
            "ck_usersettings_legislative_path_probability",
        ),
    ],
)
@pytest.mark.parametrize("invalid_value", [-0.01, 1.01])
def test_check_probability_values(test_user, property_name, check_name, invalid_value):
    settings = UserSettings.objects.get(user=test_user)

    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            setattr(settings, property_name, invalid_value)
            settings.save()

    assert str(err_proxy.value) == f"CHECK constraint failed: {check_name}"


@pytest.mark.django_db
def test_user_can_have_multiple_settings(test_user):
    UserSettings.objects.create(user=test_user, label="alternate")

    labels = set(test_user.user_settings.values_list("label", flat=True))

    assert labels == {"default", "alternate"}


@pytest.mark.django_db
def test_label_is_unique_per_user(test_user):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            UserSettings.objects.create(user=test_user, label="default")

    assert str(err_proxy.value) == (
        "UNIQUE constraint failed: common_usersettings.user_id, common_usersettings.label"
    )


@pytest.mark.django_db
def test_same_label_allowed_for_different_users(test_user, django_user_model):
    other_user = django_user_model.objects.get(username="test_staff")

    assert UserSettings.objects.filter(user=test_user, label="default").exists()
    assert UserSettings.objects.filter(user=other_user, label="default").exists()


@pytest.mark.parametrize("oob_value", [-0.01, 1.01])
def test_court_probability_for_out_of_range(test_settings, oob_value):
    with transaction.atomic():
        test_settings.court_probability_for = oob_value

        with pytest.raises(IntegrityError) as err_proxy:
            test_settings.save()

    assert (
        str(err_proxy.value)
        == "CHECK constraint failed: ck_usersettings_court_probability_for"
    )
