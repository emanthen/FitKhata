from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse
from redis import Redis
from redis.exceptions import RedisError


def healthz(request) -> JsonResponse:
    """Liveness: process is up. No dependency checks."""
    return JsonResponse({"status": "ok"})


def readyz(request) -> JsonResponse:
    """Readiness: DB and Redis are reachable."""
    checks = {"db": _check_db(), "redis": _check_redis()}
    ok = all(checks.values())
    status = 200 if ok else 503
    return JsonResponse({"status": "ok" if ok else "unavailable", "checks": checks}, status=status)


def _check_db() -> bool:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except OperationalError:
        return False


def _check_redis() -> bool:
    try:
        Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2).ping()
        return True
    except RedisError:
        return False
