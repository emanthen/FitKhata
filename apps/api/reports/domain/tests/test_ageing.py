import pytest

from reports.domain.ageing import bucket_dues_ageing


@pytest.mark.parametrize(
    ("days", "bucket"),
    [
        (0, "0-30"),
        (30, "0-30"),
        (31, "31-60"),
        (60, "31-60"),
        (61, "60+"),
        (365, "60+"),
    ],
)
def test_bucket_boundaries(days: int, bucket: str) -> None:
    assert bucket_dues_ageing(days) == bucket
