from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["*"]
SECRET_KEY = "test-secret-key"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Deterministic — tests never need a secret real key, just a valid Fernet one.
FIELD_ENCRYPTION_KEY = "WXB9Pox4knjQYZsZtMrdwMMWLWFK3igbXQJPueG3B1w="

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
