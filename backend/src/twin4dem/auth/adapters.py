from types import SimpleNamespace

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .policy import email_is_allowed

DOMAIN_NOT_ALLOWED_MESSAGE = _("This email domain is not allowed.")


class DomainRestrictedAccountAdapter(DefaultAccountAdapter):
    def clean_email(self, email):
        email = super().clean_email(email)
        if not email_is_allowed(email, settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS):
            raise ValidationError(DOMAIN_NOT_ALLOWED_MESSAGE)
        return email

    def pre_login(
        self,
        request,
        user,
        *,
        email_verification,
        signal_kwargs,
        email,
        signup,
        redirect_url,
    ):
        response = super().pre_login(
            request,
            user,
            email_verification=email_verification,
            signal_kwargs=signal_kwargs,
            email=email,
            signup=signup,
            redirect_url=redirect_url,
        )
        if response:
            return response

        if not email_is_allowed(user.email, settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS):
            messages.error(request, DOMAIN_NOT_ALLOWED_MESSAGE)
            return HttpResponseRedirect(reverse("account_login"))

        return None


class DomainRestrictedSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        super().pre_social_login(request, sociallogin)

        email = _extract_social_email(sociallogin)
        if email_is_allowed(email, settings.ACCOUNT_ALLOWED_EMAIL_DOMAINS):
            return None

        messages.error(request, DOMAIN_NOT_ALLOWED_MESSAGE)
        raise ImmediateHttpResponse(HttpResponseRedirect(reverse("account_login")))


def _extract_social_email(sociallogin) -> str:
    user_email = getattr(
        getattr(sociallogin, "user", SimpleNamespace(email="")), "email", ""
    )
    if user_email:
        return user_email

    for email_address in getattr(sociallogin, "email_addresses", []):
        email = getattr(email_address, "email", "")
        if email:
            return email

    account = getattr(sociallogin, "account", None)
    extra_data = getattr(account, "extra_data", {}) or {}
    return extra_data.get("email", "")
