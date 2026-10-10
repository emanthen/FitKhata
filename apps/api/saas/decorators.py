"""FR-11.2's @requires_feature decorator — the codebase's existing gates are
all BasePermission subclasses (accounts/permissions.py), but this is what
the task explicitly asks for, and it's a five-line wrapper.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from rest_framework.exceptions import PermissionDenied

from saas.services import has_feature


def requires_feature(key: str) -> Callable:
    def decorator(view_method: Callable) -> Callable:
        @wraps(view_method)
        def wrapper(self: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
            if request.gym is None or not has_feature(request.gym.org, key):
                raise PermissionDenied(f"'{key}' is not available on your plan.")
            return view_method(self, request, *args, **kwargs)

        return wrapper

    return decorator
