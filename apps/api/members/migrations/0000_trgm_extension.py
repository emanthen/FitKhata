"""Must run before 0001_initial's GIN trigram indexes — gin_trgm_ops only
exists once pg_trgm is enabled.
"""

from __future__ import annotations

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True
    dependencies: list[tuple[str, str]] = []
    operations = [TrigramExtension()]
