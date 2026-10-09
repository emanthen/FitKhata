"""Private, short-lived-signed-URL storage for progress photos only. The
repo-wide default STORAGES backend (config/settings/base.py) leaves
AWS_QUERYSTRING_EXPIRE unset, so django-storages' own 3600s default applies
everywhere else — too long for sensitive body photos. Nothing else in the
app uses this; it is deliberately not the default backend.

Matches config/settings/base.py's own conditional exactly: that file only
switches the *default* STORAGES backend to S3Storage when
AWS_STORAGE_BUCKET_NAME is actually set, leaving Django's built-in
FileSystemStorage for local dev/test. A plain `class PrivateMediaStorage
(S3Storage)` would ignore that and always try a real S3 connection — which
fails hard (empty bucket name) in dev/test. get_private_media_storage() is
a factory (passed as FileField's `storage=`, which accepts a zero-arg
callable and calls it lazily) so the same fallback applies here too.
"""

from __future__ import annotations

from django.conf import settings
from django.core.files.storage import Storage
from storages.backends.s3 import S3Storage


def get_private_media_storage() -> Storage:
    if getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""):
        return S3Storage(querystring_expire=300)
    from django.core.files.storage import FileSystemStorage

    return FileSystemStorage(location=str(settings.BASE_DIR / "media" / "private"))
