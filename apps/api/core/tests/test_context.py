"""Regression test for a real bug: system_context()/tenant_context()'s
cleanup used to unconditionally RESET ROLE / clear app.gym_ids, which
breaks as soon as either is nested — a common pattern wherever a test
wraps a service function (that itself opens its own system_context()) in
its own outer context for fixture setup. See core/context.py's depth-
counter fix.
"""

from __future__ import annotations

import pytest
from django.db import connection

from core.context import system_context, tenant_context

pytestmark = pytest.mark.django_db

GYM_A = "11111111-1111-1111-1111-111111111111"
GYM_B = "22222222-2222-2222-2222-222222222222"


def _current_role() -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_role")
        return cursor.fetchone()[0]


def _current_gym_ids() -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.gym_ids', true)")
        return cursor.fetchone()[0] or ""


def test_nested_system_context_does_not_reset_role_early():
    with system_context():
        assert _current_role() == "fitkhata_system"
        with system_context():
            assert _current_role() == "fitkhata_system"
        # Still lexically inside the outer context — the inner call's exit
        # must not have reset it already.
        assert _current_role() == "fitkhata_system"
    assert _current_role() != "fitkhata_system"


def test_nested_tenant_context_does_not_clear_gym_ids_early():
    with tenant_context([GYM_A]):
        assert _current_gym_ids() == GYM_A
        with tenant_context([GYM_B]):
            pass
        # Still inside the outer context — must not have been cleared by
        # the inner (nested) call's exit.
        assert _current_gym_ids() == GYM_A
    assert _current_gym_ids() == ""


def test_exception_inside_system_context_does_not_leak_depth():
    """A real regression: the depth counter must be restored even when
    the block raises, or every later system_context() call on this thread
    silently thinks it's still nested and never touches the role again.
    Each pytest-django test runs its own fresh transaction, but within a
    single test a raise-then-retry pattern (or just two independent
    system_context() calls, as below) must not see this leak.
    """
    with pytest.raises(ValueError):
        with system_context():
            raise ValueError("boom")

    # Must behave like a normal top-level call: switches role, and then
    # actually resets it back on a clean exit.
    with system_context():
        assert _current_role() == "fitkhata_system"
    assert _current_role() != "fitkhata_system"


def test_exception_inside_system_context_does_not_attempt_db_cleanup():
    """The regression this file exists to catch: a naive finally-based
    rewrite attempts RESET ROLE even after the block raised, which fails
    on the connection's already-aborted transaction and masks the real
    exception with a generic TransactionManagementError instead.
    """
    with pytest.raises(ValueError, match="boom"):
        with system_context():
            raise ValueError("boom")
