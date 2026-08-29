import pytest


@pytest.mark.django_db
def test_admin_index_has_back_to_site_link(client, admin_user):
    client.force_login(admin_user)

    response = client.get("/admin/")

    assert response.status_code == 200
    content = response.content.decode()
    assert 'href="/"' in content
    assert "Back to site" in content
