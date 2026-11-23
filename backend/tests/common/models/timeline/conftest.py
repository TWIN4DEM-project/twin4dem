from collections.abc import Callable

import pytest

from common.models import Country

from .stub_app.models import StubSubject


@pytest.fixture
def make_stub_subject(france) -> Callable[..., StubSubject]:
    def make(
        label: str = "stub",
        *,
        group: str = "group",
        country: Country | None = None,
    ) -> StubSubject:
        return StubSubject.objects.create(
            country=country or france,
            group=group,
            label=label,
        )

    return make


@pytest.fixture
def stub_subject(make_stub_subject) -> StubSubject:
    return make_stub_subject()
