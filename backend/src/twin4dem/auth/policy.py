from collections.abc import Iterable

from django.core.exceptions import ImproperlyConfigured


def normalize_allowed_email_domains(domains: Iterable[str] | None) -> list[str]:
    if domains is None:
        return []

    normalized = []
    for domain in domains:
        candidate = str(domain).strip().lower()
        if not candidate:
            continue
        _validate_domain_label(candidate)
        normalized.append(candidate)

    return normalized


def email_is_allowed(email: str, allowed_domains: Iterable[str] | None) -> bool:
    rules = normalize_allowed_email_domains(allowed_domains)
    if not rules:
        return True

    parts = email.rsplit("@", 1)
    if len(parts) != 2:
        return False

    email_domain = parts[1].strip().lower()
    if not email_domain:
        return False

    for rule in rules:
        if email_domain == rule or email_domain.endswith(f".{rule}"):
            return True

    return False


def _validate_domain_label(domain: str) -> None:
    if not domain or "." not in domain:
        raise ImproperlyConfigured(
            "ACCOUNT_ALLOWED_EMAIL_DOMAINS entries must be fully qualified domain "
            f"names, got '{domain}'."
        )

    if domain.startswith(".") or domain.endswith("."):
        raise ImproperlyConfigured(
            "ACCOUNT_ALLOWED_EMAIL_DOMAINS supports plain domain suffixes like "
            f"'example.com', got '{domain}'."
        )
