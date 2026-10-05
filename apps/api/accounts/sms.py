"""SMS provider interface, so swapping providers never touches call sites.
Selected via the SMS_PROVIDER setting (env-driven)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SmsProvider(ABC):
    @abstractmethod
    def send(self, phone: str, message: str) -> None: ...


class ConsoleSmsProvider(SmsProvider):
    """Dev default: logs instead of sending, so OTP codes are visible in
    `docker compose logs api` without needing a real SMS account."""

    def send(self, phone: str, message: str) -> None:
        logger.info("SMS to %s: %s", phone, message)


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


def get_sms_provider() -> SmsProvider:
    provider = getattr(settings, "SMS_PROVIDER", "console")
    if provider == "sparrow":
        return SparrowSmsProvider(
            token=settings.SPARROW_SMS_TOKEN, identity=settings.SPARROW_SMS_IDENTITY
        )
    return ConsoleSmsProvider()
