"""Role-permission matrix. This is this implementation's own interpretation
of the role hierarchy (docs/SRS.md 2.2 wasn't available) — see the module
docstring in accounts/permissions.py.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from accounts.permissions import IsFrontDeskOrAbove, IsManagerOrAbove, IsOwner, IsTrainer

ROLES = ["owner", "manager", "front_desk", "trainer", None]

# permission class -> {role: expected}
MATRIX = {
    IsOwner: {"owner": True, "manager": False, "front_desk": False, "trainer": False, None: False},
    IsManagerOrAbove: {
        "owner": True,
        "manager": True,
        "front_desk": False,
        "trainer": False,
        None: False,
    },
    IsFrontDeskOrAbove: {
        "owner": True,
        "manager": True,
        "front_desk": True,
        "trainer": False,
        None: False,
    },
    IsTrainer: {
        "owner": False,
        "manager": False,
        "front_desk": False,
        "trainer": True,
        None: False,
    },
}


@pytest.mark.parametrize("permission_class", list(MATRIX))
@pytest.mark.parametrize("role", ROLES)
def test_role_permission_matrix(permission_class, role):
    request = SimpleNamespace(role=role)
    expected = MATRIX[permission_class][role]
    assert permission_class().has_permission(request, view=None) is expected
