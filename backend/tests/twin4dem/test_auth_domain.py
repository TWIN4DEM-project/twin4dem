from types import SimpleNamespace

import pytest
from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.urls import reverse

from twin4dem.auth.adapters import DomainRestrictedAccountAdapter
from twin4dem.auth.adapters import DomainRestrictedSocialAccountAdapter
from twin4dem.auth.policy import email_is_allowed
from twin4dem.auth.policy import normalize_allowed_email_domains

pytestmark = pytest.mark.django_db


@pytest.fixture
def allowlist_settings(settings):
    settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS = []
    return settings


@pytest.fixture
def request_with_messages(rf):
    django_request = rf.get("/accounts/login/")
    SessionMiddleware(lambda _django_request: None).process_request(django_request)
    django_request.session.save()
    setattr(django_request, "_messages", FallbackStorage(django_request))
    return django_request


@pytest.fixture
def account_adapter(request_with_messages):
    return DomainRestrictedAccountAdapter(request_with_messages)


@pytest.fixture
def social_adapter(request_with_messages):
    return DomainRestrictedSocialAccountAdapter(request_with_messages)


@pytest.fixture
def user_factory(django_user_model, db):
    def _make(**overrides):
        defaults = {
            "username": overrides.pop("username", "allowed-user"),
            "email": overrides.pop("email", "user@example.com"),
            "is_active": overrides.pop("is_active", True),
        }
        return django_user_model.objects.create_user(
            password="password123", **defaults, **overrides
        )

    return _make


def test_normalize_allowed_email_domains_accepts_plain_domains():
    result = normalize_allowed_email_domains(
        [" Example.com ", "", "sub.example.com", "partner.org"]
    )

    assert result == ["example.com", "sub.example.com", "partner.org"]


def test_normalize_allowed_email_domains_rejects_invalid_entries():
    with pytest.raises(ValidationError):
        normalize_allowed_email_domains([".example.com", "localhost"])


def test_email_is_allowed_returns_true_when_allowlist_is_empty():
    assert email_is_allowed("user@anywhere.org", [])


@pytest.mark.parametrize("email", ["not-an-email", "user@", "@example.com"])
def test_email_is_allowed_rejects_invalid_email_syntax(email):
    assert email_is_allowed(email, ["example.com"]) is False


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("user@example.com", True),
        ("user@sub.example.com", True),
        ("user@dept.partner.org", True),
        ("user@partner.org", True),
        ("user@blocked.org", False),
        ("user@badexample.com", False),
        ("USER@EXAMPLE.COM", True),
    ],
)
def test_email_is_allowed_matches_suffix_rules(email, expected):
    allowed_domains = ["example.com", "partner.org"]

    assert email_is_allowed(email, allowed_domains) is expected


def test_clean_email_rejects_disallowed_addresses(account_adapter, allowlist_settings):
    allowlist_settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS = ["example.com"]

    with pytest.raises(ValidationError):
        account_adapter.clean_email("user@blocked.org")


def test_clean_email_accepts_allowed_addresses(account_adapter, allowlist_settings):
    allowlist_settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS = ["example.com"]

    email = account_adapter.clean_email("User@team.example.com")

    assert email_is_allowed(email, allowlist_settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS)


def test_pre_login_redirects_disallowed_users(
    account_adapter, allowlist_settings, request_with_messages, user_factory
):
    allowlist_settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS = ["example.com"]
    user = user_factory(username="blocked-login", email="user@blocked.org")

    response = account_adapter.pre_login(
        request_with_messages,
        user,
        email_verification="optional",
        signal_kwargs={},
        email=user.email,
        signup=False,
        redirect_url=None,
    )

    assert response.status_code == 302
    assert response.url == reverse("account_login")


def test_pre_login_allows_matching_users(
    account_adapter, allowlist_settings, request_with_messages, user_factory
):
    allowlist_settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS = ["example.com"]
    user = user_factory(username="allowed-login", email="user@team.example.com")

    response = account_adapter.pre_login(
        request_with_messages,
        user,
        email_verification="optional",
        signal_kwargs={},
        email=user.email,
        signup=False,
        redirect_url=None,
    )

    assert response is None


def test_pre_social_login_rejects_disallowed_email(
    social_adapter, allowlist_settings, request_with_messages
):
    allowlist_settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS = ["example.com"]
    sociallogin = SimpleNamespace(
        user=SimpleNamespace(email="user@blocked.org"),
        email_addresses=[],
        account=SimpleNamespace(extra_data={"email": "user@blocked.org"}),
    )

    with pytest.raises(ImmediateHttpResponse) as exc_info:
        social_adapter.pre_social_login(request_with_messages, sociallogin)

    assert exc_info.value.response.status_code == 302
    assert exc_info.value.response.url == reverse("account_login")


def test_pre_social_login_rejects_missing_email(
    social_adapter, allowlist_settings, request_with_messages
):
    allowlist_settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS = ["example.com"]
    sociallogin = SimpleNamespace(
        user=SimpleNamespace(email=""),
        email_addresses=[],
        account=SimpleNamespace(extra_data={}),
    )

    with pytest.raises(ImmediateHttpResponse):
        social_adapter.pre_social_login(request_with_messages, sociallogin)


def test_pre_social_login_allows_suffix_matches(
    social_adapter, allowlist_settings, request_with_messages
):
    allowlist_settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS = ["example.com"]
    sociallogin = SimpleNamespace(
        user=SimpleNamespace(email="user@team.example.com"),
        email_addresses=[],
        account=SimpleNamespace(extra_data={"email": "user@team.example.com"}),
    )

    assert social_adapter.pre_social_login(request_with_messages, sociallogin) is None
