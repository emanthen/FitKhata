from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from coaching.models import ClientProfile
from coaching.services import create_client_profile, set_health_data_consent
from coaching.tasks import generate_weekly_coaching_reports
from core.context import system_context
from gyms.models import Gym, Organization
from members.services import register_member

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Coaching Task Test Org")
        return Gym.objects.create(org=org, code="CTT1", name="Coaching Task Test Gym")


def test_enqueues_one_client_task_per_opted_in_profile_and_never_calls_anthropic(gym):
    with system_context():
        opted_in_member = register_member(gym, full_name="Opted In", phone="+9779800000040")
        opted_in_profile = create_client_profile(
            opted_in_member,
            trainer=None,
            primary_goal=ClientProfile.Goal.WEIGHT_LOSS,
            starting_weight_kg=Decimal("80.00"),
            target_weight_kg=Decimal("70.00"),
        )
        set_health_data_consent(opted_in_profile, True)

        opted_out_member = register_member(gym, full_name="Opted Out", phone="+9779800000041")
        opted_out_profile = create_client_profile(
            opted_out_member,
            trainer=None,
            primary_goal=ClientProfile.Goal.WEIGHT_LOSS,
            starting_weight_kg=Decimal("80.00"),
            target_weight_kg=Decimal("70.00"),
        )
        # consent_health_data defaults to False — never called set_health_data_consent

    with (
        patch("coaching.tasks.generate_client_coaching_report.delay") as mock_delay,
        patch("coaching.ai.call_anthropic") as mock_anthropic,
    ):
        enqueued = generate_weekly_coaching_reports()

    assert enqueued == 1
    mock_delay.assert_called_once()
    called_profile_id = mock_delay.call_args.args[0]
    assert called_profile_id == str(opted_in_profile.pk)
    assert called_profile_id != str(opted_out_profile.pk)
    # The batch task itself must never touch the Anthropic path — only
    # .delay() a separate task (see tasks.py's module docstring).
    mock_anthropic.assert_not_called()
