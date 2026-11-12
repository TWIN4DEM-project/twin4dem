
import re

import pytest
from django.contrib.staticfiles import finders


@pytest.fixture
def admin_page(client, django_user_model, db):
    user = django_user_model.objects.create_user(
        **{
            django_user_model.USERNAME_FIELD:
                "theme-staff@example.com"
        },
        password="test-password-123",
    )
    user.is_staff = True
    user.save()

    client.force_login(user)
    return client.get("/admin/")


@pytest.fixture
def shared_css():
    path = finders.find("variables.css")
    assert path is not None, "Shared variables.css not found"

    with open(path, encoding="utf-8") as css_file:
        return css_file.read()


@pytest.fixture
def admin_theme_css():
    path = finders.find("admin_theme.css")
    assert path is not None, "Admin theme CSS not found"

    with open(path, encoding="utf-8") as css_file:
        return css_file.read()


def test_admin_loads_shared_variables(admin_page):
    assert admin_page.status_code == 200
    assert "variables.css" in admin_page.content.decode()


def test_admin_loads_theme_css(admin_page):
    assert admin_page.status_code == 200
    assert "admin_theme.css" in admin_page.content.decode()


@pytest.mark.parametrize(
    "token",
    [
        "--twin-primary",
        "--twin-dashboard-bg",
        "--twin-text",
        "--twin-surface",
    ],
)
def test_shared_design_tokens_exist(shared_css, token):
    assert re.search(
        rf"{re.escape(token)}\s*:",
        shared_css,
    )


@pytest.mark.parametrize(
    "admin_token, shared_token",
    [
        ("--primary", "--twin-primary"),
        ("--body-bg", "--twin-dashboard-bg"),
        ("--header-bg", "--twin-card-bg"),
    ],
)
def test_admin_theme_uses_shared_tokens(
    admin_theme_css,
    admin_token,
    shared_token,
):
    pattern = (
        rf"{re.escape(admin_token)}\s*:\s*"
        rf"var\(\s*{re.escape(shared_token)}\s*\)"
    )

    assert re.search(pattern, admin_theme_css)


def test_shared_css_is_loaded_before_admin_theme(admin_page):
    content = admin_page.content.decode()

    variables_position = content.find("variables.css")
    theme_position = content.find("admin_theme.css")

    assert variables_position != -1
    assert theme_position != -1
    assert variables_position < theme_position
