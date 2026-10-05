"""Tenant scoping for code that runs outside a request: Celery tasks and
management commands. CLAUDE.md rule 3.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from django.db import connection, transaction

# Depth counters, not plain booleans: a call that itself runs under one of
# these contexts (e.g. a test fixture wrapping a service function that
# internally opens its own system_context()) nests. Only the OUTERMOST
# call should actually touch the session role/gym_ids — an inner call
# resetting it on exit would prematurely undo the outer context for
# whatever runs next, even though lexically still "inside" it. Thread-
# local because a DB connection (and therefore its session-level role/
# set_config state) is itself thread-local in Django.
_local = threading.local()


def _depth(name: str) -> int:
    return getattr(_local, name, 0)


def _set_depth(name: str, value: int) -> None:
    setattr(_local, name, value)


@contextmanager
def tenant_context(gym_ids: list[str]) -> Iterator[None]:
    """Scope the DB session to the given gyms for the duration of the block."""
    depth = _depth("tenant")
    with transaction.atomic():
        if depth == 0:
            with connection.cursor() as cursor:
                ids_csv = ",".join(str(i) for i in gym_ids)
                cursor.execute("SELECT set_config('app.gym_ids', %s, true)", [ids_csv])
        _set_depth("tenant", depth + 1)
        succeeded = False
        try:
            yield
            succeeded = True
        finally:
            # Depth bookkeeping must always happen, exception or not — a
            # leaked depth would silently disable every later call on this
            # thread, which already bit this file once (see test below for
            # the exact nesting scenario). The actual DB reset, below, is
            # separate and deliberately conditioned on `succeeded`.
            _set_depth("tenant", depth)
            if succeeded and depth == 0:
                # Only reached when the block didn't raise. SET LOCAL/
                # set_config(...,true) only auto-resets at the *outermost*
                # transaction's commit — a nested call (already inside
                # another atomic()) only gets a savepoint, which doesn't
                # undo it on release — so the outermost context resets
                # explicitly rather than let it leak into whatever runs
                # next in that same outer transaction. On an exception,
                # skip this entirely: the connection may already be
                # unusable until rollback (attempting another query here
                # would itself raise and mask the real exception), and
                # transaction.atomic()'s own rollback-to-savepoint undoes
                # the set_config change anyway.
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('app.gym_ids', '', true)")


@contextmanager
def system_context() -> Iterator[None]:
    """Cross-tenant reads/jobs that must see every gym: billing sweeps,
    retention jobs, TenantMiddleware's own gym-resolution lookup, and
    accounts.tokens.issue_tokens_for_user's claim-building StaffRole query —
    all inherently need to see across tenants before any single-gym RLS
    context exists to query within.

    Requires `GRANT fitkhata_system TO fitkhata_app` (see infra/initdb and
    infra/postgres/initdb) so the app role is permitted to assume it.
    """
    depth = _depth("system")
    with transaction.atomic():
        if depth == 0:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE fitkhata_system")
        _set_depth("system", depth + 1)
        succeeded = False
        try:
            yield
            succeeded = True
        finally:
            _set_depth("system", depth)
            # Same reasoning as tenant_context's reset — see that docstring.
            if succeeded and depth == 0:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")
