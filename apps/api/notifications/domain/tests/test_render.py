from __future__ import annotations

from notifications.domain.render import render


def test_substitutes_a_single_variable():
    assert render("Hi {{name}}!", {"name": "Ram"}) == "Hi Ram!"


def test_substitutes_multiple_variables():
    body = "{{name}}, your plan expires in {{days}} day(s)."
    assert render(body, {"name": "Sita", "days": 3}) == "Sita, your plan expires in 3 day(s)."


def test_missing_variable_renders_empty_string_not_an_error():
    assert render("Hi {{name}}!", {}) == "Hi !"


def test_no_variables_returns_body_unchanged():
    assert render("Welcome to FitKhata.", {}) == "Welcome to FitKhata."


def test_tolerates_whitespace_inside_braces():
    assert render("Hi {{ name }}!", {"name": "Hari"}) == "Hi Hari!"
