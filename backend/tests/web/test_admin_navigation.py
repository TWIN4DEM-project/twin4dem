import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.test import Client
from django.urls import reverse


# ==================================================
# POINT 1 - ADMIN NAVIGATION
# ==================================================


@pytest.fixture
def admin_page(admin_client: Client):
    return admin_client.get(reverse("admin:index"))


def test_admin_page_loads(admin_page):
    assert admin_page.status_code == 200


def test_admin_has_back_to_site_link(admin_page):
    content = admin_page.content.decode()

    assert "Back to site" in content
    assert re.search(
        r'<a[^>]*href=["\']/["\'][^>]*>',
        content,
    )


def test_admin_preserves_default_branding(admin_page):
    content = admin_page.content.decode()

    assert 'id="site-name"' in content


# ==================================================
# POINT 3 - SHARED THEME
# ==================================================


@pytest.mark.parametrize(
    "stylesheet",
    [
        "variables.css",
        "admin_theme.css",
    ],
)
def test_admin_stylesheet_exists(stylesheet: str):
    assert finders.find(stylesheet) is not None


def test_admin_loads_theme_stylesheets(admin_page):
    content = admin_page.content.decode()

    assert "variables.css" in content
    assert "admin_theme.css" in content


@pytest.mark.parametrize(
    "page",
    [
        "account_login",
        "account_logout",
    ],
)
def test_auth_pages_load_shared_theme(
    page: str,
    client: Client,
    admin_client: Client,
):
    test_client = admin_client if page == "account_logout" else client

    response = test_client.get(reverse(page))

    assert response.status_code == 200
    assert b"variables.css" in response.content


@pytest.fixture
def theme_variables():
    path = finders.find("css/variables.css")

    assert path is not None

    return Path(path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "variable",
    [
        "--twin-bg",
        "--twin-primary",
        "--twin-primary-soft",
        "--twin-text",
        "--twin-surface",
    ],
)
def test_shared_theme_variable_exists(
    theme_variables: str,
    variable: str,
):
    assert re.search(
        rf"{re.escape(variable)}\s*:",
        theme_variables,
    )
