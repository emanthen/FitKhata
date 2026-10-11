from .base import *  # noqa: F403
from .base import env  # noqa: F401

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# base.py's SECRET_KEY has a hardcoded dev-only fallback ("insecure-dev-key-
# change-me") so local dev never needs a .env to boot -- that fallback is
# itself now public (committed in this repo's history), so prod must never
# be allowed to silently inherit it. No default here: a missing
# DJANGO_SECRET_KEY crashes startup instead of running with a known key
# (which would let anyone forge a valid signed member-pass token, among
# other things -- django.core.signing derives from SECRET_KEY).
SECRET_KEY = env("DJANGO_SECRET_KEY")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
