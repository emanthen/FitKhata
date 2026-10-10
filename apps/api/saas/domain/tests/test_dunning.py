from __future__ import annotations

import pytest

from saas.domain.dunning import next_status


@pytest.mark.parametrize(
    "current_status,days,expected",
    [
        ("active", 0, "grace"),
        ("grace", 2, None),
        ("grace", 3, None),
        ("grace", 7, None),
        ("grace", 8, "read_only"),
        ("grace", 15, "read_only"),
        ("read_only", 8, None),
        ("read_only", 29, None),
        ("read_only", 30, "suspended"),
        ("suspended", 45, None),
        ("trial", 10, None),
        ("cancelled", 10, None),
    ],
)
def test_next_status_boundaries(current_status, days, expected):
    assert next_status(current_status, days) == expected
