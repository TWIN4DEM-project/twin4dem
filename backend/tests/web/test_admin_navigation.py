
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def user_factory(db):
    def create_user(email, is_staff=False):
        User = get_user_model()

        user = User.objects.create_user(
            **{User.USERNAME_FIELD: email},
            password="test-password-123",
        )
        user.is_staff = is_staff
        user.save()

        return user

    return create_user


@pytest.fixture
def staff_user(user_factory):
    return user_factory("staff@example.com", is_staff=True)


@pytest.fixture
def regular_user(user_factory):
    return user_factory("regular@example.com")


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.fixture
def regular_client(client, regular_user):
    client.force_login(regular_user)
    return client


def test_staff_sees_admin_link(staff_client):
    response = staff_client.get("/")

    assert response.status_code == 200
    assert 'href="/admin/"' in response.content.decode()


def test_regular_user_does_not_see_admin_link(regular_client):
    response = regular_client.get("/")

    assert response.status_code == 200
    assert 'href="/admin/"' not in response.content.decode()


def test_anonymous_user_does_not_see_admin_link(client):
    response = client.get("/")

    assert response.status_code == 200
    assert 'href="/admin/"' not in response.content.decode()


def test_staff_can_access_admin(staff_client):
    response = staff_client.get(reverse("admin:index"))

    assert response.status_code == 200


def test_regular_user_cannot_access_admin(regular_client):
    response = regular_client.get(reverse("admin:index"))

    assert response.status_code in (302, 403)


@pytest.mark.parametrize(
    "url",
    [
        "/admin/",
        "/admin/auth/group/",
    ],
)
def test_admin_has_back_to_site_link(staff_client, url):
    response = staff_client.get(url)

    assert response.status_code == 200
    assert "Back to site" in response.content.decode()
    assert 'href="/"' in response.content.decode()


def test_settings_deep_link_is_removed(staff_client):
    response = staff_client.get("/")

    assert response.status_code == 200
    assert 'href="/admin/common/usersettings/"' not in response.content.decode()


@pytest.mark.parametrize(
    "url",
    [
        "/admin/",
        "/admin/auth/group/",
    ],
)
def test_admin_has_twin4dem_branding(staff_client, url):
    response = staff_client.get(url)

    assert response.status_code == 200
    assert "TWIN4DEM" in response.content.decode()
    assert "Django administration" not in response.content.decode()
