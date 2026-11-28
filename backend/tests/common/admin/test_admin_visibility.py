from datetime import UTC, datetime

import pytest
from django.contrib.admin.sites import site
from django.test import RequestFactory

from common.admin import (
    CountryAdmin,
    InstitutionAdmin,
    PartyAdmin,
    UserSettingsAdmin,
)
from common.admin._institution import InstitutionTimeFrameInlineForm
from common.admin._party import PartyPositionInline
from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    InstitutionTimeFrame,
    Party,
    PartyPosition,
    UserSettings,
)
from common.session import set_current_settings


def admin_request(rf, user):
    request = rf.get("/admin/")
    request.user = user
    return request


def select_settings(client, user_settings):
    request = RequestFactory().get("/admin/")
    request.session = client.session
    set_current_settings(request, user_settings)
    request.session.save()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_admin_class,model,owned_rows",
    [
        (UserSettingsAdmin, UserSettings, 1),
        (CountryAdmin, Country, 0),
        (InstitutionAdmin, Institution, 0),
        (PartyAdmin, Party, 0),
    ],
)
def test_non_superuser_sees_only_their_own_rows(
    staff_user, admin_user, rf, model_admin_class, model, owned_rows
):
    view = model_admin_class(model, site)

    own = view.get_queryset(admin_request(rf, staff_user))
    everything = view.get_queryset(admin_request(rf, admin_user))

    assert own.count() == owned_rows
    assert everything.count() == model.objects.count()


def formfield_of(model_admin_class, model, field_name, request):
    view = model_admin_class(model, site)
    db_field = model._meta.get_field(field_name)
    return view.formfield_for_foreignkey(db_field, request)


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
    staff_user, admin_user, rf, model_admin_class, model, field_name, owned_rows
):
    restricted = formfield_of(
        model_admin_class, model, field_name, admin_request(rf, staff_user)
    )
    unrestricted = formfield_of(
        model_admin_class, model, field_name, admin_request(rf, admin_user)
    )
    total = model._meta.get_field(field_name).related_model.objects.count()

    assert restricted.queryset.count() == owned_rows
    assert unrestricted.queryset.count() == total


@pytest.mark.django_db
def test_chamber_choices_are_restricted_to_the_owning_user(staff_user, admin_user, rf):
    inline = PartyPositionInline(PartyPosition, site)
    db_field = PartyPosition._meta.get_field("chamber")

    restricted = inline.formfield_for_foreignkey(
        db_field, admin_request(rf, staff_user)
    )
    every = inline.formfield_for_foreignkey(db_field, admin_request(rf, admin_user))

    assert restricted.queryset.count() == 0
    assert (
        every.queryset.count()
        == Institution.objects.filter(
            kind__branch=InstitutionBranch.LEGISLATIVE
        ).count()
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "parent_fixture,url",
    [
        ("cabinet", "/admin/common/institution/{pk}/change/"),
        ("renaissance", "/admin/common/party/{pk}/change/"),
    ],
)
def test_inline_uses_the_selected_settings(
    admin_client, admin_user, parent_fixture, url, request
):
    parent = request.getfixturevalue(parent_fixture)
    selected = UserSettings.objects.create(user=admin_user, label="selected")
    select_settings(admin_client, selected)

    response = admin_client.get(url.format(pk=parent.pk))

    formset = response.context["inline_admin_formsets"][0].formset
    assert set(formset.empty_form.fields["timeline_selection"].queryset) == set(
        selected.timelines.all()
    )


@pytest.mark.django_db
def test_form_prefills_timelines_of_a_saved_frame(cabinet, alternate_timeline):
    frame = InstitutionTimeFrame.objects.create_for(
        cabinet, valid_from=datetime(2020, 1, 1, tzinfo=UTC)
    )
    frame.timelines.add(alternate_timeline)

    form = InstitutionTimeFrameInlineForm(instance=frame)

    assert list(form.initial["timeline_selection"]) == [alternate_timeline]
