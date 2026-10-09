"""Fixture payloads for coaching/tests/test_ai.py — mocked Anthropic
responses covering the happy path and the failure modes the FR explicitly
calls out (malformed JSON, wrong shape).
"""

from __future__ import annotations

VALID_JSON = """{"summary": "Solid progress this week, slight dip in protein.", \
"suggestions": [{"type": "diet", "text_en": "Add an extra protein source.", \
"text_ne": "थप प्रोटिन स्रोत थप्नुहोस्।", "reason": "low_protein"}]}"""

# Truncated, invalid JSON.
MALFORMED_JSON = '{"summary": "Solid progress", "suggestions": [{"type": "diet", '

# Missing the required "suggestions" key.
WRONG_SHAPE_JSON = '{"summary": "Solid progress this week."}'
