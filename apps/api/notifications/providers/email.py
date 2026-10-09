"""Thin wrapper over Django's own SMTP client — no new client code needed."""

from __future__ import annotations

from smtplib import SMTPException

from django.core.mail import send_mail

from notifications.providers.base import ProviderTransientError


def send(to_email: str, subject: str, body: str) -> None:
    try:
        send_mail(subject, body, None, [to_email])
    except SMTPException as exc:
        raise ProviderTransientError(str(exc)) from exc
