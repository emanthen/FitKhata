from __future__ import annotations

import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from core.validators import (
    MAX_IMAGE_SIZE_BYTES,
    MAX_IMPORT_FILE_SIZE_BYTES,
    MAX_PDF_SIZE_BYTES,
    strip_exif,
    validate_image_file,
    validate_import_file_size,
    validate_pdf_file,
)

EXIF_MODEL_TAG = 0x0110  # "Model" -- a plain string-valued tag, not a nested-IFD
# pointer like GPSInfo, so it round-trips simply; stands in for the kind of
# device/location metadata a real photo's EXIF can carry.


def _jpeg_bytes_with_exif() -> bytes:
    image = Image.new("RGB", (10, 10), color="red")
    exif = image.getexif()
    exif[EXIF_MODEL_TAG] = "fake-device-with-gps"
    buf = io.BytesIO()
    image.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _upload(name: str, content: bytes, content_type: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type=content_type)


def test_validate_image_file_accepts_a_real_image():
    upload = _upload("photo.jpg", _jpeg_bytes_with_exif(), "image/jpeg")
    validate_image_file(upload)  # must not raise


def test_validate_image_file_rejects_a_renamed_non_image():
    upload = _upload("photo.jpg", b"this is not an image, just text", "image/jpeg")
    with pytest.raises(ValidationError, match="not a valid image"):
        validate_image_file(upload)


def test_validate_image_file_rejects_an_oversized_file():
    upload = _upload("photo.jpg", b"x" * (MAX_IMAGE_SIZE_BYTES + 1), "image/jpeg")
    with pytest.raises(ValidationError, match="under"):
        validate_image_file(upload)


def test_strip_exif_removes_gps_metadata():
    upload = _upload("photo.jpg", _jpeg_bytes_with_exif(), "image/jpeg")
    original = Image.open(io.BytesIO(upload.read()))
    assert EXIF_MODEL_TAG in original.getexif()  # sanity: the fixture really has it

    cleaned = strip_exif(upload)
    reopened = Image.open(io.BytesIO(cleaned.read()))

    assert EXIF_MODEL_TAG not in reopened.getexif()


def test_validate_pdf_file_accepts_a_real_pdf_header():
    upload = _upload("waiver.pdf", b"%PDF-1.4 fake but has the header", "application/pdf")
    validate_pdf_file(upload)  # must not raise


def test_validate_pdf_file_rejects_a_renamed_non_pdf():
    upload = _upload("waiver.pdf", b"not actually a pdf", "application/pdf")
    with pytest.raises(ValidationError, match="not a valid PDF"):
        validate_pdf_file(upload)


def test_validate_pdf_file_rejects_an_oversized_file():
    upload = _upload("waiver.pdf", b"%PDF-" + b"x" * MAX_PDF_SIZE_BYTES, "application/pdf")
    with pytest.raises(ValidationError, match="under"):
        validate_pdf_file(upload)


def test_validate_import_file_size_rejects_an_oversized_file():
    upload = _upload("members.csv", b"x" * (MAX_IMPORT_FILE_SIZE_BYTES + 1), "text/csv")
    with pytest.raises(ValidationError, match="under"):
        validate_import_file_size(upload)


def test_validate_import_file_size_accepts_a_normal_file():
    upload = _upload("members.csv", b"full_name,phone\nRam,9800000001\n", "text/csv")
    validate_import_file_size(upload)  # must not raise
