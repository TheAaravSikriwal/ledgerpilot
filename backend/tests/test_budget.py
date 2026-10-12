from datetime import date

from ledgerpilot.budget import BudgetTxn, compute_budget, find_upcoming_bills


def txn(d, merchant, cents, cat, status="personal", pct=0):
    return BudgetTxn(
        date=d,
        merchant=merchant,
        amount_cents=cents,
        category_id=cat,
        business_status=status,
        business_pct=pct,
    )


def line(result, cid):
    return next(c for c in result.categories if c.category_id == cid)


def test_pace_statuses_mid_month(categories):
    targets = {"dining": 600_00, "groceries": 900_00, "shopping": 300_00}
    month = [
        txn(date(2026, 10, 3), "SWEETGREEN", -200_00, "dining"),  # expected 300 by day 15
        txn(date(2026, 10, 4), "WHOLE FOODS", -500_00, "groceries"),  # expected 450 → hot
        txn(date(2026, 10, 5), "TARGET", -320_00, "shopping"),  # over target
    ]
    r = compute_budget(2026, 10, date(2026, 10, 15), targets, categories, month, [])
    assert line(r, "dining").status == "on_track"
    assert line(r, "groceries").status == "running_hot"
    assert line(r, "shopping").status == "over"
    assert line(r, "dining").expected_by_today_cents == 290_32  # 600 * 15/31


def test_business_share_excluded_and_review_counts_in_fallback(categories):
    targets = {"phone_internet": 200_00, "subscriptions": 50_00}
    month = [
        txn(date(2026, 10, 7), "VERIZON", -100_00, "phone_internet", "business", 40),
        txn(date(2026, 10, 5), "GITHUB", -21_00, "software_saas", "review", 100),
        txn(date(2026, 10, 6), "ADOBE", -59_99, "software_saas", "business", 100),
    ]
    r = compute_budget(2026, 10, date(2026, 10, 10), targets, categories, month, [])
    assert line(r, "phone_internet").spent_cents == 60_00
    assert line(r, "subscriptions").spent_cents == 21_00


def test_refunds_reduce_spending(categories):
    month = [
        txn(date(2026, 10, 2), "TARGET", -80_00, "shopping"),
        txn(date(2026, 10, 9), "TARGET", 30_00, "shopping"),
    ]
    r = compute_budget(2026, 10, date(2026, 10, 10), {"shopping": 500_00}, categories, month, [])
    assert line(r, "shopping").spent_cents == 50_00


def test_unbudgeted_groups_ignored(categories):
    month = [
        txn(date(2026, 10, 2), "PAYROLL", 4000_00, "paycheck"),
        txn(date(2026, 10, 2), "AUTOPAY", -900_00, "card_payment"),
        txn(date(2026, 10, 2), "GUSTO", -6000_00, "officer_comp", "business", 100),
    ]
    r = compute_budget(2026, 10, date(2026, 10, 10), {"dining": 100_00}, categories, month, [])
    assert r.spent_cents == 0


def history_rent_and_netflix():
    rows = []
    for m in (6, 7, 8, 9):
        rows.append(txn(date(2026, m, 1), "AVALONBAY", -3150_00, "housing"))
        rows.append(txn(date(2026, m, 20), "NETFLIX", -22_99, "subscriptions"))
    rows.append(txn(date(2026, 9, 11), "OLEANA", -140_00, "dining"))  # one-off
    return rows


def test_recurring_bills_detected(categories):
    month = [txn(date(2026, 10, 1), "AVALONBAY", -3150_00, "housing")]
    bills = find_upcoming_bills(date(2026, 10, 15), month, history_rent_and_netflix(), categories)
    assert [(b.merchant, b.expected_day, b.amount_cents) for b in bills] == [("NETFLIX", 20, 22_99)]


def test_irregular_amounts_not_recurring(categories):
    history = [
        txn(date(2026, 6, 18), "EVERSOURCE", -60_00, "utilities"),
        txn(date(2026, 7, 18), "EVERSOURCE", -150_00, "utilities"),
        txn(date(2026, 8, 18), "EVERSOURCE", -95_00, "utilities"),
    ]
    assert find_upcoming_bills(date(2026, 10, 5), [], history, categories) == []


def test_recurring_bill_already_paid_does_not_look_hot(categories):
    # Rent lands on the 1st; linear pacing would flag it as running hot all month.
    month = [txn(date(2026, 10, 1), "AVALONBAY", -3150_00, "housing")]
    r = compute_budget(
        2026,
        10,
        date(2026, 10, 5),
        {"housing": 3200_00},
        categories,
        month,
        history_rent_and_netflix(),
    )
    housing = line(r, "housing")
    assert housing.expected_by_today_cents == 3150_00 + round(50_00 * 5 / 31)
    assert housing.status == "on_track"


def test_safe_to_spend_formula(categories):
    targets = {"housing": 3200_00, "subscriptions": 50_00, "dining": 600_00}
    month = [
        txn(date(2026, 10, 1), "AVALONBAY", -3150_00, "housing"),
        txn(date(2026, 10, 4), "TATTE", -100_00, "dining"),
    ]
    r = compute_budget(
        2026, 10, date(2026, 10, 15), targets, categories, month, history_rent_and_netflix()
    )
    # remaining = 3850 - 3250 - 22.99 upcoming = 577.01 over 17 days (15th..31st)
    assert r.upcoming_bills_cents == 22_99
    assert r.days_remaining == 17
    assert r.safe_to_spend_today_cents == 577_01 // 17


def test_safe_to_spend_floors_at_zero(categories):
    month = [txn(date(2026, 10, 2), "TARGET", -900_00, "shopping")]
    r = compute_budget(2026, 10, date(2026, 10, 10), {"shopping": 500_00}, categories, month, [])
    assert r.safe_to_spend_today_cents == 0


def test_past_month_is_closed(categories):
    month = [txn(date(2026, 9, 2), "TARGET", -100_00, "shopping")]
    r = compute_budget(2026, 9, date(2026, 10, 10), {"shopping": 500_00}, categories, month, [])
    assert r.days_remaining == 0
    assert r.safe_to_spend_today_cents == 0
    assert line(r, "shopping").expected_by_today_cents == 500_00


def test_daily_series_tracks_cumulative_spend_and_pace(categories):
    month = [
        txn(date(2026, 10, 1), "AVALONBAY", -3150_00, "housing"),
        txn(date(2026, 10, 3), "TATTE", -20_00, "dining"),
    ]
    r = compute_budget(
        2026,
        10,
        date(2026, 10, 5),
        {"housing": 3200_00, "dining": 310_00},
        categories,
        month,
        history_rent_and_netflix(),
    )
    assert len(r.daily) == 31
    assert [p.spent_cents for p in r.daily[:5]] == [3150_00, 3150_00, 3170_00, 3170_00, 3170_00]
    assert r.daily[5].spent_cents is None  # the future
    assert r.daily[0].pace_cents == 3150_00 + round(50_00 / 31) + 10_00
    assert r.daily[-1].pace_cents == 3510_00
