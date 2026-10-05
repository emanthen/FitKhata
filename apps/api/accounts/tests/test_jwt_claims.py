from __future__ import annotations

import pytest
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from core.context import system_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner_with_gym():
    from gyms.models import Gym, Organization

    with system_context():
        org = Organization.objects.create(name="Claims Org")
        gym = Gym.objects.create(org=org, code="C1", name="Claims Gym")
        user = User.objects.create_user(phone="+9772000000001", password="x")
        StaffRole.objects.create(user=user, org=org, gym=gym, role=StaffRole.Role.OWNER)
    return user, org, gym


def test_access_token_has_org_gym_role_claims(owner_with_gym):
    user, org, gym = owner_with_gym
    tokens = issue_tokens_for_user(user)
    access = AccessToken(tokens["access"])

    assert access["org_id"] == str(org.id)
    assert access["gym_ids"] == [str(gym.id)]
    assert access["role"] == "owner"


def test_user_with_no_staff_role_gets_empty_claims():
    user = User.objects.create_user(phone="+9772000000002", password="x")
    tokens = issue_tokens_for_user(user)
    access = AccessToken(tokens["access"])

    assert access["org_id"] is None
    assert access["gym_ids"] == []
    assert access["role"] is None


def test_owner_without_totp_requires_setup(owner_with_gym):
    user, _org, _gym = owner_with_gym
    tokens = issue_tokens_for_user(user)
    assert tokens["requires_totp_setup"] is True


def test_non_owner_does_not_require_totp_setup():
    from gyms.models import Gym, Organization

    with system_context():
        org = Organization.objects.create(name="Claims Org 2")
        gym = Gym.objects.create(org=org, code="C2", name="Claims Gym 2")
        user = User.objects.create_user(phone="+9772000000003", password="x")
        StaffRole.objects.create(user=user, org=org, gym=gym, role=StaffRole.Role.TRAINER)

    tokens = issue_tokens_for_user(user)
    assert tokens["requires_totp_setup"] is False
