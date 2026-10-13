from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_member_pass_rate_limits_after_the_configured_threshold():
    """AllowAny, no auth beyond the signed token itself (attendance/views.py's
    MemberPassView docstring) — the request-volume backstop for that.
    """
    client = APIClient()
    cache.clear()
    try:
        statuses = []
        for _ in range(70):  # rate is 60/m -- stop well past it or on first 429
            response = client.get("/api/v1/m/pass/not-a-real-token")
            statuses.append(response.status_code)
            if response.status_code == 429:
                break
        assert 429 in statuses
    finally:
        cache.clear()
