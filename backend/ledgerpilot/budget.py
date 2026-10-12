"""Monthly budget with daily pace and "safe to spend today". Pure functions — no DB access.

Only household (personal-owner) transactions in essential/discretionary categories count:
- confirmed business items count only their personal share (100 - business_pct)
- items still in business review count in full under their category's personal fallback
"""

import calendar
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from statistics import median

from .models import BUDGET_GROUPS, Category
from .money import pct_of

HOT_PACE_RATIO = 1.10
RECURRING_LOOKBACK_MONTHS = 4
RECURRING_MIN_MONTHS = 3
RECURRING_AMOUNT_TOLERANCE = 0.15


@dataclass(frozen=True)
class BudgetTxn:
    date: date
    merchant: str
    amount_cents: int
    category_id: str
    business_status: str
    business_pct: int


@dataclass
class CategoryLine:
    category_id: str
    name: str
    group: str
    target_cents: int
    spent_cents: int
    expected_by_today_cents: int
    status: str


@dataclass(frozen=True)
class UpcomingBill:
    merchant: str
    category_id: str
    expected_day: int
    amount_cents: int


@dataclass(frozen=True)
class DailyPoint:
    day: int
    spent_cents: int | None  # cumulative; None for days that haven't happened yet
    pace_cents: int  # cumulative spending that would keep the month on budget


@dataclass
class BudgetResult:
    year: int
    month: int
    today: date
    days_in_month: int
    days_remaining: int
    target_cents: int
    spent_cents: int
    expected_by_today_cents: int
    upcoming_bills_cents: int
    safe_to_spend_today_cents: int
    status: str
    categories: list[CategoryLine] = field(default_factory=list)
    upcoming_bills: list[UpcomingBill] = field(default_factory=list)
    daily: list[DailyPoint] = field(default_factory=list)


def counted(t: BudgetTxn, categories: Mapping[str, Category]) -> tuple[str, int] | None:
    """(budget category, spending cents) for a transaction, or None if it doesn't count.

    Spending is positive for outflows, negative for refunds.
    """
    cat = categories.get(t.category_id)
    if cat is None:
        return None
    if t.business_status == "review" and cat.group == "business":
        cid, spend = cat.personal_fallback_id, -t.amount_cents
    elif t.business_status == "business":
        cid, spend = cat.id, pct_of(-t.amount_cents, 100 - t.business_pct)
    else:
        cid, spend = cat.id, -t.amount_cents
    if cid is None or categories[cid].group not in BUDGET_GROUPS:
        return None
    return cid, spend


def pace_status(spent: int, target: int, expected: int) -> str:
    if spent > target:
        return "over"
    if spent > expected * HOT_PACE_RATIO:
        return "running_hot"
    return "on_track"


def _month_index(d: date) -> int:
    return d.year * 12 + d.month - 1


def _posted_merchants(month_txns: Sequence[BudgetTxn], categories) -> set[str]:
    return {t.merchant for t in month_txns if (c := counted(t, categories)) and c[1] > 0}


def find_upcoming_bills(
    today: date,
    month_txns: Sequence[BudgetTxn],
    history_txns: Sequence[BudgetTxn],
    categories: Mapping[str, Category],
) -> list[UpcomingBill]:
    """Recurring bills expected later this month that have not posted yet."""
    posted = _posted_merchants(month_txns, categories)
    recurring = find_recurring(_month_index(today), history_txns, categories)
    return [b for b in recurring if b.merchant not in posted and b.expected_day > today.day]


def find_recurring(
    month_index: int, history_txns: Sequence[BudgetTxn], categories: Mapping[str, Category]
) -> list[UpcomingBill]:
    """Merchants seen in ≥3 of the previous 4 months with stable amounts."""
    current = month_index
    monthly: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    first_day: dict[str, dict[int, int]] = defaultdict(dict)
    merchant_cat: dict[str, str] = {}
    for t in history_txns:
        m = _month_index(t.date)
        if not (current - RECURRING_LOOKBACK_MONTHS <= m < current):
            continue
        c = counted(t, categories)
        if c is None or c[1] <= 0:
            continue
        monthly[t.merchant][m] += c[1]
        first_day[t.merchant][m] = min(first_day[t.merchant].get(m, 31), t.date.day)
        merchant_cat[t.merchant] = c[0]

    bills: list[UpcomingBill] = []
    for merchant, sums in monthly.items():
        if len(sums) < RECURRING_MIN_MONTHS:
            continue
        typical = median(sums.values())
        if any(abs(v - typical) > typical * RECURRING_AMOUNT_TOLERANCE for v in sums.values()):
            continue
        day = int(median(first_day[merchant].values()))
        bills.append(UpcomingBill(merchant, merchant_cat[merchant], day, round(typical)))
    return sorted(bills, key=lambda b: (b.expected_day, b.merchant))


def compute_budget(
    year: int,
    month: int,
    today: date,
    targets: Mapping[str, int],
    categories: Mapping[str, Category],
    month_txns: Sequence[BudgetTxn],
    history_txns: Sequence[BudgetTxn],
) -> BudgetResult:
    days_in_month = calendar.monthrange(year, month)[1]
    target_index, today_index = year * 12 + month - 1, _month_index(today)
    if target_index < today_index:
        elapsed, days_remaining = days_in_month, 0
    elif target_index > today_index:
        elapsed, days_remaining = 0, days_in_month
    else:
        elapsed, days_remaining = today.day, days_in_month - today.day + 1

    spent: dict[str, int] = defaultdict(int)
    spent_by_day: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t in month_txns:
        c = counted(t, categories)
        if c is not None:
            spent[c[0]] += c[1]
            spent_by_day[t.date.day][c[0]] += c[1]

    # Recurring bills are lump sums: pace them by due date, and the rest of the target linearly.
    recurring: list[UpcomingBill] = []
    recurring_total: dict[str, int] = defaultdict(int)
    recurring_due: dict[str, int] = defaultdict(int)
    if target_index <= today_index:
        posted = _posted_merchants(month_txns, categories)
        recurring = find_recurring(target_index, history_txns, categories)
        for bill in recurring:
            recurring_total[bill.category_id] += bill.amount_cents
            if bill.merchant in posted or bill.expected_day <= elapsed:
                recurring_due[bill.category_id] += bill.amount_cents

    lines: list[CategoryLine] = []
    for cid in sorted(set(targets) | set(spent), key=lambda c: categories[c].sort_order or 0):
        cat = categories[cid]
        target = targets.get(cid, 0)
        flexible = max(0, target - recurring_total[cid])
        expected = min(target, recurring_due[cid] + round(flexible * elapsed / days_in_month))
        lines.append(
            CategoryLine(
                cid,
                cat.name,
                cat.group,
                target,
                spent[cid],
                expected,
                pace_status(spent[cid], target, expected),
            )
        )

    bills: list[UpcomingBill] = []
    if target_index == today_index:
        bills = [
            b
            for b in find_upcoming_bills(today, month_txns, history_txns, categories)
            if b.category_id in targets
        ]

    daily = _daily_series(lines, recurring, recurring_total, spent_by_day, days_in_month, elapsed)
    total_target = sum(line.target_cents for line in lines)
    total_spent = sum(line.spent_cents for line in lines)
    total_expected = sum(line.expected_by_today_cents for line in lines)
    upcoming = sum(b.amount_cents for b in bills)
    safe = 0
    if days_remaining > 0:
        safe = max(0, total_target - total_spent - upcoming) // days_remaining
    return BudgetResult(
        year=year,
        month=month,
        today=today,
        days_in_month=days_in_month,
        days_remaining=days_remaining,
        target_cents=total_target,
        spent_cents=total_spent,
        expected_by_today_cents=total_expected,
        upcoming_bills_cents=upcoming,
        safe_to_spend_today_cents=safe,
        status=pace_status(total_spent, total_target, total_expected),
        categories=lines,
        upcoming_bills=bills,
        daily=daily,
    )


def _daily_series(
    lines: Sequence[CategoryLine],
    recurring: Sequence[UpcomingBill],
    recurring_total: Mapping[str, int],
    spent_by_day: Mapping[int, Mapping[str, int]],
    days_in_month: int,
    elapsed: int,
) -> list[DailyPoint]:
    """Cumulative actual spending vs. the on-budget pace, one point per day of the month."""
    budgeted = {line.category_id for line in lines}
    points: list[DailyPoint] = []
    cumulative = 0
    for day in range(1, days_in_month + 1):
        cumulative += sum(v for cid, v in spent_by_day.get(day, {}).items() if cid in budgeted)
        pace = 0
        for line in lines:
            due = sum(
                b.amount_cents
                for b in recurring
                if b.category_id == line.category_id and b.expected_day <= day
            )
            flexible = max(0, line.target_cents - recurring_total.get(line.category_id, 0))
            pace += min(line.target_cents, due + round(flexible * day / days_in_month))
        points.append(DailyPoint(day, cumulative if day <= elapsed else None, pace))
    return points
