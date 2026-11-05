from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from django.contrib.auth.models import Permission

from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    InstitutionKind,
    TimeFrame,
    VirtualTimeline,
)


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


@pytest.fixture
def user_kind(userland) -> InstitutionKind:
    return InstitutionKind.objects.create(
        country=userland,
        branch=InstitutionBranch.EXECUTIVE,
        institution_name="cabinet",
    )


@pytest.fixture
def senate_kind() -> InstitutionKind:
    """Testland's senate, without institutions."""
    return InstitutionKind.objects.create(
        country_id=1,
        branch=InstitutionBranch.LEGISLATIVE,
        institution_name="senate",
    )


def _midnight(date: str | None) -> datetime | None:
    """Midnight UTC of `date` ('YYYY-MM-DD'), or None."""
    return datetime.fromisoformat(date).replace(tzinfo=UTC) if date else None


@pytest.fixture
def make_senate(senate_kind) -> Callable[..., Institution]:
    """
    Creates a senate of Testland. Given a bound ('YYYY-MM-DD'), it occupies one
    time frame on all timelines; otherwise it is frameless.
    """

    def make(
        label: str, valid_from: str | None = None, valid_to: str | None = None
    ) -> Institution:
        institution = Institution.objects.create(
            kind=senate_kind, label=label, size=136
        )
        if valid_from or valid_to:
            TimeFrame.objects.occupy(
                institution, _midnight(valid_from), _midnight(valid_to)
            )
        return institution

    return make


@pytest.fixture
def alternate_timeline(test_settings) -> VirtualTimeline:
    return VirtualTimeline.objects.create(
        user_settings=test_settings, label="alternate"
    )


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
