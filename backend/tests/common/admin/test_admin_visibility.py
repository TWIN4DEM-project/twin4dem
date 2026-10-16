import pytest
from django.contrib.admin.sites import site
from django.test import RequestFactory

from common.admin import (
    CountryAdmin,
    InstitutionAdmin,
    PartyAdmin,
    TimeFrameAdmin,
    UserSettingsAdmin,
)
from common.admin._party import PartyPositionInline
from common.admin._timeframe import TimeFrameAdminForm
from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    Party,
    PartyPosition,
    TimeFrame,
    UserSettings,
    VirtualTimeline,
)


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(
        username="clerk", password="clerk-pass", is_staff=True
    )


def make_request(user):
    request = RequestFactory().get("/admin/")
    request.user = user
    return request


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_admin_class,model,owned_rows",
    [
        (UserSettingsAdmin, UserSettings, 1),
        (CountryAdmin, Country, 0),
        (InstitutionAdmin, Institution, 0),
        (PartyAdmin, Party, 0),
        (TimeFrameAdmin, TimeFrame, 0),
    ],
)
def test_non_superuser_sees_only_their_own_rows(
    staff_user, django_user_model, model_admin_class, model, owned_rows
):
    admin_user = django_user_model.objects.get(username="test_admin")
    view = model_admin_class(model, site)

    own = view.get_queryset(make_request(staff_user))
    everything = view.get_queryset(make_request(admin_user))

    assert own.count() == owned_rows
    assert everything.count() == model.objects.count()


def formfield_of(model_admin_class, model, field_name, user):
    view = model_admin_class(model, site)
    db_field = model._meta.get_field(field_name)
    return view.formfield_for_foreignkey(db_field, make_request(user))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_admin_class,model,field_name,owned_rows",
    [
        (PartyAdmin, Party, "country", 0),
        (CountryAdmin, Country, "user_settings", 1),
        (InstitutionAdmin, Institution, "kind", 0),
    ],
)
def test_foreign_key_choices_are_restricted_to_the_owning_user(
    staff_user, django_user_model, model_admin_class, model, field_name, owned_rows
):
    admin_user = django_user_model.objects.get(username="test_admin")

    restricted = formfield_of(model_admin_class, model, field_name, staff_user)
    unrestricted = formfield_of(model_admin_class, model, field_name, admin_user)
    total = model._meta.get_field(field_name).related_model.objects.count()

    assert restricted.queryset.count() == owned_rows
    assert unrestricted.queryset.count() == total


@pytest.mark.django_db
def test_chamber_choices_are_restricted_to_the_owning_user(
    staff_user, django_user_model
):
    admin_user = django_user_model.objects.get(username="test_admin")
    inline = PartyPositionInline(PartyPosition, site)
    db_field = PartyPosition._meta.get_field("chamber")

    restricted = inline.formfield_for_foreignkey(db_field, make_request(staff_user))
    every = inline.formfield_for_foreignkey(db_field, make_request(admin_user))

    assert restricted.queryset.count() == 0
    assert (
        every.queryset.count()
        == Institution.objects.filter(
            kind__branch=InstitutionBranch.LEGISLATIVE
        ).count()
    )


@pytest.mark.django_db
def test_superuser_form_leaves_all_timeline_choices(django_user_model):
    admin_user = django_user_model.objects.get(username="test_admin")
    view = TimeFrameAdmin(TimeFrame, site)

    form = view.get_form(make_request(admin_user))()

    assert form.fields["timeline_selection"].queryset.count() == (
        VirtualTimeline.objects.count()
    )


@pytest.mark.django_db
def test_staff_form_restricts_timeline_choices(staff_user):
    view = TimeFrameAdmin(TimeFrame, site)

    form = view.get_form(make_request(staff_user))()

    assert list(form.fields["timeline_selection"].queryset) == list(
        VirtualTimeline.objects.filter(user_settings__user=staff_user)
    )


@pytest.mark.django_db
def test_form_prefills_timelines_of_a_saved_frame(cabinet, alternate_timeline):
    from datetime import UTC, datetime

    frame = TimeFrame.objects.create_for(
        cabinet, valid_from=datetime(2020, 1, 1, tzinfo=UTC)
    )
    frame.timelines.add(alternate_timeline)

    form = TimeFrameAdminForm(instance=frame)

    assert list(form.initial["timeline_selection"]) == [alternate_timeline]


def test_form_leaves_timelines_blank_for_a_new_frame():
    form = TimeFrameAdminForm(instance=TimeFrame())

    assert "timeline_selection" not in form.initial
