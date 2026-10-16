import pytest
from django.db import IntegrityError, transaction

from common.models import UserSettings, VirtualTimeline


@pytest.mark.django_db
def test_new_user_gets_default_timeline(django_user_model):
    user = django_user_model.objects.create(username="new_user")

    settings = UserSettings.objects.get(user=user)

    assert list(settings.timelines.values_list("label", flat=True)) == ["default"]


@pytest.mark.django_db
def test_new_settings_get_default_timeline(test_settings):
    other_settings = UserSettings.objects.create(
        user=test_settings.user, label="alternate world"
    )

    assert list(other_settings.timelines.values_list("label", flat=True)) == ["default"]


@pytest.mark.django_db
def test_updating_settings_does_not_add_timelines(test_settings):
    test_settings.data_update_frequency = 20
    test_settings.save()

    assert test_settings.timelines.count() == 1


@pytest.mark.django_db
def test_settings_can_have_multiple_timelines(test_settings):
    VirtualTimeline.objects.create(user_settings=test_settings, label="alternate")

    labels = set(test_settings.timelines.values_list("label", flat=True))

    assert labels == {"default", "alternate"}


@pytest.mark.django_db
def test_timeline_label_is_unique_per_settings(test_settings):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            VirtualTimeline.objects.create(user_settings=test_settings, label="default")

    assert str(err_proxy.value) == (
        "UNIQUE constraint failed: "
        "common_virtualtimeline.user_settings_id, common_virtualtimeline.label"
    )


@pytest.mark.django_db
def test_deleting_settings_deletes_timelines(test_settings):
    settings_id = test_settings.id

    test_settings.delete()

    assert not VirtualTimeline.objects.filter(user_settings_id=settings_id).exists()
