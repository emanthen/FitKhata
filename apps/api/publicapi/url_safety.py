"""SSRF protection for webhook subscription URLs — the only place this
codebase fetches a user-supplied URL from the server (publicapi.tasks's
deliver_webhook). Checked twice, deliberately: once at subscription-create
time (fail fast, good UX) and again immediately before every delivery
attempt (publicapi.tasks.deliver_webhook) — a hostname that resolved to a
public IP at create time can be repointed at a private/metadata address by
the time delivery actually runs (DNS rebinding), so only the second check
is actually load-bearing for security; the first is a convenience.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeWebhookUrl(Exception):
    pass


def assert_safe_webhook_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeWebhookUrl("Webhook URL must be http or https.")
    hostname = parsed.hostname
    if not hostname:
        raise UnsafeWebhookUrl("Webhook URL has no hostname.")

    try:
        resolved = {info[4][0] for info in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise UnsafeWebhookUrl(f"Could not resolve webhook host {hostname!r}.") from exc

    for addr in resolved:
        ip = ipaddress.ip_address(addr)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local  # covers the 169.254.169.254 cloud metadata endpoint
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeWebhookUrl(
                f"Webhook URL {hostname!r} resolves to a disallowed address ({addr})."
            )
