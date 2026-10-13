from __future__ import annotations

from unittest.mock import patch

import pytest

from publicapi.url_safety import UnsafeWebhookUrl, assert_safe_webhook_url


def _resolving_to(*ips):
    return [(None, None, None, None, (ip, 443)) for ip in ips]


def test_rejects_a_non_http_scheme():
    with pytest.raises(UnsafeWebhookUrl, match="http or https"):
        assert_safe_webhook_url("ftp://example.com/hook")


def test_rejects_an_unresolvable_host():
    with pytest.raises(UnsafeWebhookUrl, match="Could not resolve"):
        assert_safe_webhook_url("https://this-host-does-not-exist.invalid/hook")


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "10.0.0.5",  # private
        "192.168.1.1",  # private
        "172.16.0.1",  # private
        "169.254.169.254",  # link-local -- the cloud metadata endpoint
        "0.0.0.0",  # unspecified
        "224.0.0.1",  # multicast
        "::1",  # loopback, IPv6
        "fe80::1",  # link-local, IPv6
    ],
)
def test_rejects_disallowed_addresses(ip):
    with patch("socket.getaddrinfo", return_value=_resolving_to(ip)):
        with pytest.raises(UnsafeWebhookUrl, match="disallowed address"):
            assert_safe_webhook_url("https://attacker-controlled.example/hook")


def test_allows_a_genuinely_public_address():
    with patch("socket.getaddrinfo", return_value=_resolving_to("93.184.216.34")):
        assert_safe_webhook_url("https://example.com/hook")  # must not raise
