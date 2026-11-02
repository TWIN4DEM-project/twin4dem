import pytest
from django.contrib.auth.models import Permission

from common.models import Country


@pytest.fixture
def user_client(request, client, test_user):
    """Logged in as test_user, with the permission codenames given as param."""
    test_user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="common",
            codename__in=getattr(request, "param", []),
        )
    )
    client.force_login(test_user)
    return client


@pytest.fixture
def userland(test_user_settings) -> Country:
    return Country.objects.create(user_settings=test_user_settings, name="Userland")


@pytest.fixture(scope="session")
def aggrandisement_batch_dirname():
    return "aggrandisement-batches"


@pytest.fixture
def aggrandisement_batch_name(request):
    return getattr(request, "param", "one-unit.json")


@pytest.fixture
def aggrandisement_batch_path(
    request, data_dir, aggrandisement_batch_dirname, aggrandisement_batch_name
):
    return data_dir / aggrandisement_batch_dirname / aggrandisement_batch_name


@pytest.fixture(scope="session")
def load_batch(aggrandisement_batch_dirname, load_json):
    def _(name: str) -> dict:
        return load_json(f"{aggrandisement_batch_dirname}/{name}")

    return _


@pytest.fixture
def aggrandisement_batch(request, load_batch, aggrandisement_batch_name):
    return load_batch(aggrandisement_batch_name)
