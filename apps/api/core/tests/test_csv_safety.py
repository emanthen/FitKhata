from __future__ import annotations

import pytest

from core.domain.csv_safety import escape_formula_prefix


@pytest.mark.parametrize(
    "value",
    [
        "=cmd|'/c calc'!A1",
        "+1+1",
        "-1+1",
        "@SUM(A1:A2)",
        "\t=1+1",
        "\r=1+1",
    ],
)
def test_escapes_formula_triggering_prefixes(value):
    assert escape_formula_prefix(value) == "'" + value


@pytest.mark.parametrize("value", ["Ram Shrestha", "9779800000001", "", "normal-text"])
def test_leaves_safe_strings_unchanged(value):
    assert escape_formula_prefix(value) == value


def test_non_string_values_pass_through_unchanged():
    assert escape_formula_prefix(None) is None
    assert escape_formula_prefix(42) == 42
    assert escape_formula_prefix(3.14) == 3.14
