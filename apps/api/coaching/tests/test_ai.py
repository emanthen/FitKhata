from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from coaching import ai
from coaching.models import ClientProfile
from coaching.services import create_client_profile, set_health_data_consent
from coaching.tests.fixtures.anthropic_responses import MALFORMED_JSON, VALID_JSON, WRONG_SHAPE_JSON
from core.context import system_context
from gyms.models import Gym, Organization
from members.services import register_member

pytestmark = pytest.mark.django_db

WEEK_START = date(2026, 10, 5)


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Coaching AI Test Org")
        return Gym.objects.create(org=org, code="CAI1", name="Coaching AI Test Gym")


@pytest.fixture
def profile(gym):
    with system_context():
        member = register_member(
            gym,
            full_name="Real Member Name",
            phone="+9779811112222",
            email="real.member@example.com",
        )
        profile = create_client_profile(
            member,
            trainer=None,
            primary_goal=ClientProfile.Goal.WEIGHT_LOSS,
            starting_weight_kg=Decimal("80.00"),
            target_weight_kg=Decimal("70.00"),
        )
        set_health_data_consent(profile, True)
        return profile


# --- parse_and_validate -------------------------------------------------------


def test_parse_and_validate_accepts_well_formed_json():
    result = ai.parse_and_validate(VALID_JSON)
    assert result is not None
    assert result.suggestions[0].type == "diet"


def test_parse_and_validate_returns_none_on_malformed_json():
    assert ai.parse_and_validate(MALFORMED_JSON) is None


def test_parse_and_validate_returns_none_on_wrong_shape():
    assert ai.parse_and_validate(WRONG_SHAPE_JSON) is None


# --- generate_weekly_report: retry-once-then-fallback ------------------------


def test_retries_once_then_falls_back_on_persistent_malformed_json(profile):
    bad_response = ai.AnthropicResponse(text=MALFORMED_JSON, input_tokens=100, output_tokens=50)
    mock_target = "coaching.ai.call_anthropic"
    with system_context(), patch(mock_target, return_value=bad_response) as mock_call:
        report = ai.generate_weekly_report(profile, WEEK_START)

    assert mock_call.call_count == 2
    assert report.model == ""  # rules-only fallback marker
    assert report.cost_npr == Decimal("0.00")
    assert len(report.suggestions) >= 1


def test_succeeds_on_second_attempt_after_one_malformed_response(profile):
    responses = [
        ai.AnthropicResponse(text=MALFORMED_JSON, input_tokens=100, output_tokens=50),
        ai.AnthropicResponse(text=VALID_JSON, input_tokens=120, output_tokens=60),
    ]
    with system_context(), patch("coaching.ai.call_anthropic", side_effect=responses) as mock_call:
        report = ai.generate_weekly_report(profile, WEEK_START)

    assert mock_call.call_count == 2
    assert report.model != ""
    assert report.cost_npr > Decimal("0.00")


def test_budget_exceeded_skips_anthropic_entirely(profile, settings):
    with system_context():
        profile.gym.settings = {**profile.gym.settings, "ai_budget_npr_monthly": 0}
        profile.gym.save(update_fields=["settings"])

        with patch("coaching.ai.call_anthropic") as mock_call:
            report = ai.generate_weekly_report(profile, WEEK_START)

    mock_call.assert_not_called()
    assert report.model == ""


# --- PII never in the prompt (the FR's explicit test requirement) ------------


def test_build_summary_payload_never_includes_pii(profile):
    with system_context():
        member = profile.member
        payload = ai._gather_client_summary(profile, WEEK_START).payload

    serialized = json.dumps(payload)
    assert member.full_name not in serialized
    assert member.phone not in serialized
    assert member.email not in serialized
    assert "full_name" not in payload and "name" not in payload
    assert "phone" not in payload and "email" not in payload
    assert payload["member_id"] == str(member.pk)  # the one allowed identifier


# --- cost computation ---------------------------------------------------------


def test_cost_npr_computed_from_usage_tokens(settings):
    settings.ANTHROPIC_USD_TO_NPR_RATE = Decimal("140.00")
    # claude-sonnet-5: $3.00/MTok in, $15.00/MTok out
    cost = ai._cost_npr("claude-sonnet-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == (Decimal("3.00") + Decimal("15.00")) * Decimal("140.00")


def test_rules_only_suggestions_always_succeeds_even_with_no_flags():
    result = ai.rules_only_suggestions([])
    assert len(result.suggestions) >= 1


def test_rules_only_suggestions_covers_every_known_flag():
    flags = ["missed_leg_day", "weight_stall", "low_protein", "low_attendance"]
    result = ai.rules_only_suggestions(flags)
    assert len(result.suggestions) == 4
