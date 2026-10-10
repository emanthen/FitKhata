"""Fixed, deterministic ids for FitKhata's own internal platform tenant —
seeded once in migrations/0003_seed_fitkhata_platform_gym.py, referenced by
id (not looked up by name) everywhere else (saas/gateways.py) so every
environment agrees on which row holds FitKhata's own merchant credentials.
"""

from __future__ import annotations

import uuid

FITKHATA_PLATFORM_ORG_ID = uuid.UUID("00000000-f17b-4a7a-8000-000000000001")
FITKHATA_PLATFORM_GYM_ID = uuid.UUID("00000000-f17b-4a7a-8000-000000000002")
