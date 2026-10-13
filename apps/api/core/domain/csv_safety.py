"""CSV/XLSX formula-injection guarding. No Django imports — see CLAUDE.md
rule 4's precedent (pure domain functions).

Excel/Sheets/LibreOffice treat a cell starting with =, +, -, @, tab, or CR
as a formula regardless of the file format (CSV or XLSX) — a value a user
typed into an import (a member's name, a phone number typo) or that an
attacker deliberately crafted can execute when the exported file is later
opened by staff, reaching out to an external URL or shelling out via
legacy Excel macro functions like =cmd (CWE-1236). Prefixing with a
leading apostrophe forces spreadsheet apps to treat the cell as plain
text while keeping the value byte-for-byte visible once opened.
"""

from __future__ import annotations

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def escape_formula_prefix(value: object) -> object:
    """Only strings starting with a formula-triggering character are
    touched — everything else (numbers, None, already-safe strings)
    passes through unchanged so exports don't silently reformat data.
    """
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value
