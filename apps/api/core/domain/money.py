"""Pure NPR money formatting. No Django imports — see CLAUDE.md rule 4."""

from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def _group_lakh(digits: str) -> str:
    """Indian/Nepali digit grouping: last 3 digits, then pairs. '1234567' -> '12,34,567'."""
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join([*groups, tail])


def format_npr(amount: Decimal, *, symbol: bool = False) -> str:
    """Format a Decimal as NPR with lakh grouping and 2 decimal places.

    format_npr(Decimal('1234567.5')) == '12,34,567.50'
    """
    quantized = amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    quantized = abs(quantized)
    int_part, _, frac_part = f"{quantized:f}".partition(".")
    frac_part = frac_part.ljust(2, "0")
    formatted = f"{sign}{_group_lakh(int_part)}.{frac_part}"
    return f"Rs. {formatted}" if symbol else formatted
