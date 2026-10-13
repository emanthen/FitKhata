"""Upload validation shared across every app that accepts a file from a
member/staff-controlled form: member photos, waiver PDFs, coaching
progress photos, CSV/XLSX imports. Size caps and real content checks —
not re-architecting storage or signing, which are already adequate (see
config/settings/base.py's AWS_QUERYSTRING_AUTH / coaching/storage.py's
private bucket + 5-minute signed URL).
"""

from __future__ import annotations

import io

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
MAX_PDF_SIZE_BYTES = 5 * 1024 * 1024
MAX_IMPORT_FILE_SIZE_BYTES = 10 * 1024 * 1024


def validate_image_file(file) -> None:
    """Pillow already a dependency — Image.open(...).verify() decodes
    enough of the file to confirm it's a real, intact image rather than
    trusting the filename extension or client-supplied content-type.
    """
    if file.size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(f"Image must be under {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB.")
    try:
        file.seek(0)
        Image.open(file).verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("File is not a valid image.") from exc
    finally:
        file.seek(0)


def validate_pdf_file(file) -> None:
    if file.size > MAX_PDF_SIZE_BYTES:
        raise ValidationError(f"File must be under {MAX_PDF_SIZE_BYTES // (1024 * 1024)} MB.")
    file.seek(0)
    header = file.read(5)
    file.seek(0)
    if header != b"%PDF-":
        raise ValidationError("File is not a valid PDF.")


def strip_exif(file) -> ContentFile:
    """Re-encodes an already-validated (validate_image_file) image through
    Pillow, dropping EXIF (which can carry GPS coordinates) — call AFTER
    validate_image_file, not instead of it: this assumes the file already
    decodes cleanly and doesn't itself guard against a corrupt/non-image
    file the way verify() does. Pillow only re-embeds EXIF on save if you
    explicitly pass it back via exif=...; omitting that kwarg here is
    what actually drops it, not a separate strip step.
    """
    file.seek(0)
    image = Image.open(file)
    image_format = image.format or "JPEG"
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    name = getattr(file, "name", None) or f"photo.{image_format.lower()}"
    return ContentFile(buffer.getvalue(), name=name)


def validate_import_file_size(file) -> None:
    if file.size > MAX_IMPORT_FILE_SIZE_BYTES:
        raise ValidationError(
            f"Import file must be under {MAX_IMPORT_FILE_SIZE_BYTES // (1024 * 1024)} MB."
        )
