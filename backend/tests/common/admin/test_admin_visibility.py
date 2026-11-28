from datetime import UTC, datetime

import pytest

from django.contrib.admin.sites import site
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.test.client import Client

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


def grant_view_permission(user, model):
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label=model._meta.app_label,
            content_type__model=model._meta.model_name,
            codename=f"view_{model._meta.model_name}",
        )
    )


def admin_request(rf, client, user):
    user_settings = user.user_settings.get()
    request = select_settings(rf, client, user_settings)
    request.user = user
    return request


def select_settings(rf, client, user_settings):
    request = rf.get("/admin/")
    request.session = client.session
    set_current_settings(request, user_settings)
    request.session.save()
    return request


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
    staff_user, admin_client, model_admin_class, model, owned_rows
):
    grant_view_permission(staff_user, model)
    staff_client = Client()
    staff_client.force_login(staff_user)

    url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
    staff_res = staff_client.get(url)
    admin_res = admin_client.get(url)

    assert staff_res.context["cl"].queryset.count() == owned_rows
    assert admin_res.context["cl"].queryset.count() == model.objects.count()


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
    staff_user,
    admin_user,
    admin_client,
    rf,
    model_admin_class,
    model,
    field_name,
    owned_rows,
):
    restricted = formfield_of(
        model_admin_class,
        model,
        field_name,
        admin_request(rf, admin_client, staff_user),
    )
    unrestricted = formfield_of(
        model_admin_class,
        model,
        field_name,
        admin_request(rf, admin_client, admin_user),
    )
    total = model._meta.get_field(field_name).related_model.objects.count()

    assert restricted.queryset.count() == owned_rows
    assert unrestricted.queryset.count() == total


@pytest.mark.django_db
def test_chamber_choices_are_restricted_to_the_owning_user(
    staff_user, admin_user, admin_client, rf
):
    inline = PartyPositionInline(PartyPosition, site)
    db_field = PartyPosition._meta.get_field("chamber")

    restricted = inline.formfield_for_foreignkey(
        db_field, admin_request(rf, admin_client, staff_user)
    )
    every = inline.formfield_for_foreignkey(
        db_field, admin_request(rf, admin_client, admin_user)
    )

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
    rf, admin_client, admin_user, parent_fixture, url, request
):
    parent = request.getfixturevalue(parent_fixture)
    selected = UserSettings.objects.create(user=admin_user, label="selected")
    select_settings(rf, admin_client, selected)

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
