"""IP-keyed rate limiting for AllowAny endpoints with no other natural key
(no api_key/user/session to key on — publicapi/views.py's own
rate_limited decorator already covers the api_key-keyed case there).
"""

from __future__ import annotations

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit


def ip_rate_limited(rate: str):
    """Class decorator for an APIView: @ip_rate_limited("60/m")."""
    return method_decorator(ratelimit(key="ip", rate=rate, block=True), name="dispatch")
