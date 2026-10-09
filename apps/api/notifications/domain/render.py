"""Template body rendering (FR-6.1/6.3). Pure Python, no Django imports.

Deliberately not Jinja2 — templates are a flat set of "{{variable}}" tokens
with no logic (conditionals/loops), so stdlib re.sub is the whole job.
"""

from __future__ import annotations

import re
from typing import Any

_VARIABLE_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render(body: str, context: dict[str, Any]) -> str:
    """A variable missing from context renders as "" rather than raising —
    a template typo or an optional field shouldn't block delivery.
    """
    return _VARIABLE_RE.sub(lambda m: str(context.get(m.group(1), "")), body)
