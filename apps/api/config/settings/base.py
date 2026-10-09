"""Settings shared by every environment. Env-specific files import * from here."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django_filters",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "corsheaders",
    "drf_spectacular",
    "storages",
    "channels",
    "django_celery_beat",
    "core",
    "accounts",
    "gyms",
    "members",
    "attendance",
    "billing",
    "retention",
    "notifications",
    "coaching",
    "staff",
    "reports",
    "saas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # As high as possible (django-cors-headers' own recommendation) — must
    # run before CommonMiddleware, which can 301/404 a request (e.g. the
    # APPEND_SLASH redirect) before CORS headers would otherwise get added.
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.TenantMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://fitkhata:fitkhata@localhost:5432/fitkhata"),
}

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    },
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Asia/Kathmandu"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Rule 5: DB stores UTC (USE_TZ=True); TIME_ZONE governs app-facing display conversion.
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kathmandu"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# File storage: Cloudflare R2 (S3-compatible) in prod when configured, else
# Django's local filesystem storage for dev. No local object-store service —
# MinIO's open-source edition was archived upstream in 2026.
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
if AWS_STORAGE_BUCKET_NAME:
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL")
    AWS_S3_ADDRESSING_STYLE = "path"
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

# The web app runs on a different origin (Next.js dev server / its own
# domain in prod) — without this, every browser request is blocked by CORS
# before it even reaches a view (confirmed: curl bypasses CORS entirely and
# never catches this, so this must be exercised from a real browser).
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])
CORS_ALLOW_HEADERS = [*default_headers, "x-gym-id"]

# This API's own public origin — for building links that go out in an SMS
# (billing/receipts.py's receipt link) rather than being resolved by a
# browser already on the right origin.
API_PUBLIC_URL = env("API_PUBLIC_URL", default="http://localhost:8000")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# SMS: "console" (dev, logs instead of sending), "sparrow" (Sparrow SMS, needs
# SPARROW_SMS_TOKEN/SPARROW_SMS_IDENTITY), or "aakash" (Aakash SMS, needs
# AAKASH_SMS_AUTH_TOKEN). See accounts/sms.py.
SMS_PROVIDER = env("SMS_PROVIDER", default="console")
SPARROW_SMS_TOKEN = env("SPARROW_SMS_TOKEN", default="")
SPARROW_SMS_IDENTITY = env("SPARROW_SMS_IDENTITY", default="")
AAKASH_SMS_AUTH_TOKEN = env("AAKASH_SMS_AUTH_TOKEN", default="")

SPECTACULAR_SETTINGS = {
    "TITLE": "FitKhata API",
    "DESCRIPTION": "Multi-tenant gym management API.",
    "VERSION": "0.1.0",
    "SERVE_URLCONF": "config.urls",
    "SCHEMA_PATH_PREFIX": "/api/v1/",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1, send_default_pii=False)

# Fernet key for per-gym payment credential encryption (core.crypto). Rule 10.
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")

# Notifications (Phase 6) — see notifications/services.py and providers/.
SMS_COST_NPR = Decimal(env("SMS_COST_NPR", default="1.50"))

WHATSAPP_CLOUD_API_TOKEN = env("WHATSAPP_CLOUD_API_TOKEN", default="")
WHATSAPP_PHONE_NUMBER_ID = env("WHATSAPP_PHONE_NUMBER_ID", default="")
WHATSAPP_APP_SECRET = env("WHATSAPP_APP_SECRET", default="")
WHATSAPP_WEBHOOK_VERIFY_TOKEN = env("WHATSAPP_WEBHOOK_VERIFY_TOKEN", default="")

VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", default="")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", default="")
VAPID_CONTACT_EMAIL = env("VAPID_CONTACT_EMAIL", default="admin@fitkhata.com")

# No EMAIL_* settings existed anywhere in this repo before Phase 6 — the
# "email (SMTP)" notification channel needs Django's standard ones. Console
# backend in dev (prints instead of sending), same spirit as SMS_PROVIDER's
# "console" default.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@fitkhata.com")

# AI coaching (Phase 7) — see coaching/ai.py.
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-sonnet-5")
# Static manual FX rate, not a live pull — not worth the complexity until
# NPR drift actually matters for a monthly AI budget this coarse.
ANTHROPIC_USD_TO_NPR_RATE = Decimal(env("ANTHROPIC_USD_TO_NPR_RATE", default="140.00"))
