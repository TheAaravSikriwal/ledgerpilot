"""Money helpers. All amounts are integer cents; negative means money out of an account."""

from decimal import ROUND_HALF_UP, Decimal


def pct_of(cents: int, *pcts: int) -> int:
    """Apply one or more whole-number percentages to `cents`, rounding half away from zero."""
    value = Decimal(cents)
    for pct in pcts:
        value = value * Decimal(pct) / Decimal(100)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def dollars(cents: int) -> str:
    """Format cents as a plain dollar string, e.g. -1234 -> '-12.34' (for CSV export)."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"
