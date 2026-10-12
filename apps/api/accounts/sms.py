"""SMS provider interface, so swapping providers never touches call sites.
Selected via the SMS_PROVIDER setting (env-driven)."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

REAL_PROVIDERS = {"sparrow", "aakash"}


def validate_sms_provider(value: str) -> None:
    """config/settings/prod.py calls this once at import time — a plain
    function rather than inline settings-module code so it's unit-testable
    without reimporting Django settings. "console" (the dev default)
    silently logs OTP codes; prod must never fall back to it silently.
    """
    if value not in REAL_PROVIDERS:
        raise ImproperlyConfigured(
            f"SMS_PROVIDER must be one of {sorted(REAL_PROVIDERS)} in production, "
            f"got {value!r} — the 'console' default logs OTP codes."
        )


class SmsProvider(ABC):
    @abstractmethod
    def send(self, phone: str, message: str) -> None: ...


def _mask_digits(value: str) -> str:
    return re.sub(r"\d{3,}", lambda m: "*" * len(m.group()), value)


class ConsoleSmsProvider(SmsProvider):
    """Dev default: logs instead of sending, so OTP codes are visible in
    `docker compose logs api` without needing a real SMS account. Masks
    digit runs (OTP codes, phone numbers) unless DEBUG — prod.py's
    validate_sms_provider() call means this should never actually run in
    prod, but a misconfigured staging env with DEBUG off is exactly the
    case this exists to not leak codes into logs for.
    """

    def send(self, phone: str, message: str) -> None:
        if settings.DEBUG:
            logger.info("SMS to %s: %s", phone, message)
        else:
            logger.info("SMS to %s: %s", _mask_digits(phone), _mask_digits(message))


class SparrowSmsProvider(SmsProvider):
    """https://sparrowsms.com/ — the common SMS gateway for Nepali numbers."""

    API_URL = "https://api.sparrowsms.com/v2/sms/"

    def __init__(self, token: str, identity: str) -> None:
        self.token = token
        self.identity = identity

    def send(self, phone: str, message: str) -> None:
        local_number = phone.removeprefix("+977")
        response = requests.post(
            self.API_URL,
            data={"token": self.token, "from": self.identity, "to": local_number, "text": message},
            timeout=10,
        )
        response.raise_for_status()


class AakashSmsProvider(SmsProvider):
    """https://aakashsms.com/ — the other common Nepali SMS gateway,
    notifications/ needs a second provider behind this same interface so a
    gym isn't tied to a single upstream (FR-6.3). to takes a bare 10-digit
    local number, same convention as Sparrow's API.
    """

    API_URL = "https://sms.aakashsms.com/sms/v3/send"

    def __init__(self, auth_token: str) -> None:
        self.auth_token = auth_token

    def send(self, phone: str, message: str) -> None:
        local_number = phone.removeprefix("+977")
        response = requests.post(
            self.API_URL,
            data={"auth_token": self.auth_token, "to": local_number, "text": message},
            timeout=10,
        )
        response.raise_for_status()


def get_sms_provider() -> SmsProvider:
    provider = getattr(settings, "SMS_PROVIDER", "console")
    if provider == "sparrow":
        return SparrowSmsProvider(
            token=settings.SPARROW_SMS_TOKEN, identity=settings.SPARROW_SMS_IDENTITY
        )
    if provider == "aakash":
        return AakashSmsProvider(auth_token=settings.AAKASH_SMS_AUTH_TOKEN)
    return ConsoleSmsProvider()
