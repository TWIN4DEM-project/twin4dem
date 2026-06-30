from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.core.validators import DomainNameValidator
from django.core.validators import EmailValidator

validate_domain_name = DomainNameValidator()
validate_email_address = EmailValidator()


def normalize_allowed_email_domains(domains: Iterable[str] | None) -> list[str]:
    if domains is None:
        return []

    normalized = []
    for domain in domains:
        candidate = str(domain).strip().lower()
        if not candidate:
            continue
        validate_domain_name(candidate)
        normalized.append(candidate)

    return normalized


def email_is_allowed(email: str, allowed_domains: Iterable[str] | None) -> bool:
    rules = normalize_allowed_email_domains(allowed_domains)
    if not rules:
        return True

    try:
        validate_email_address(email)
    except ValidationError:
        return False

    email_domain = email.rsplit("@", 1)[1].lower()

    return any(
        email_domain == rule or email_domain.endswith(f".{rule}") for rule in rules
    )
