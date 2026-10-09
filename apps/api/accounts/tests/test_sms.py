from __future__ import annotations

from unittest.mock import Mock, patch

from accounts.sms import AakashSmsProvider, ConsoleSmsProvider, SparrowSmsProvider, get_sms_provider


def test_get_sms_provider_defaults_to_console(settings):
    settings.SMS_PROVIDER = "console"
    assert isinstance(get_sms_provider(), ConsoleSmsProvider)


def test_get_sms_provider_returns_sparrow_when_configured(settings):
    settings.SMS_PROVIDER = "sparrow"
    settings.SPARROW_SMS_TOKEN = "tok"
    settings.SPARROW_SMS_IDENTITY = "ident"
    assert isinstance(get_sms_provider(), SparrowSmsProvider)


def test_get_sms_provider_returns_aakash_when_configured(settings):
    settings.SMS_PROVIDER = "aakash"
    settings.AAKASH_SMS_AUTH_TOKEN = "tok"
    assert isinstance(get_sms_provider(), AakashSmsProvider)


def test_aakash_sends_a_local_number_without_the_977_prefix():
    provider = AakashSmsProvider(auth_token="test-token")
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None

    with patch("accounts.sms.requests.post", return_value=mock_response) as mock_post:
        provider.send("+9779800000001", "Hello")

    mock_post.assert_called_once_with(
        AakashSmsProvider.API_URL,
        data={"auth_token": "test-token", "to": "9800000001", "text": "Hello"},
        timeout=10,
    )
