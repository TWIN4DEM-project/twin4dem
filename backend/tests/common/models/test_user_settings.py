import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.models import UserSettings, PartySettings


@pytest.mark.django_db
def test_create_default_user_settings(test_user):
    settings = UserSettings.objects.get(user=test_user)

    assert settings is not None
    assert settings.id > 0
    assert settings.user.username == "testuser"
    assert settings.label == "default"
    assert settings.government_size == 15
    assert settings.government_connectivity_degree == 3
    assert settings.parliament_size == 100
    assert settings.court_size == 5
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
def test_check_too_few_total_party_members(test_user):
    settings = UserSettings.objects.get(user=test_user)

    with pytest.raises(ValidationError) as err_proxy:
        with transaction.atomic():
            all_party_settings = PartySettings.objects.filter(
                user_settings=settings
            ).first()
            all_party_settings.delete()
            settings.clean()

    assert err_proxy.value.message_dict == {
        "parliament_size": [
            "Sum of party member_count (75) must equal parliament_size (100).",
        ]
    }


@pytest.mark.django_db
def test_check_too_many_total_party_members(test_user):
    settings = UserSettings.objects.get(user=test_user)

    with pytest.raises(ValidationError) as err_proxy:
        with transaction.atomic():
            settings.parties.create(
                label="extra", member_count=1, position="opposition"
            )
            settings.clean()

    assert err_proxy.value.message_dict == {
        "parliament_size": [
            "Sum of party member_count (101) must equal parliament_size (100).",
        ]
    }


@pytest.mark.django_db
def test_check_change_party_members(test_user):
    settings = UserSettings.objects.get(user=test_user)

    with pytest.raises(ValidationError) as err_proxy:
        with transaction.atomic():
            party_settings = settings.parties.first()
            party_settings.member_count += 1
            party_settings.save()

            settings.clean()

    assert err_proxy.value.message_dict == {
        "parliament_size": [
            "Sum of party member_count (101) must equal parliament_size (100).",
        ]
    }
