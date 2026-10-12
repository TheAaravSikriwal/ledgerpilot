from datetime import date, timedelta

from ledgerpilot.money import pct_of
from ledgerpilot.sources.mock import MIXED_USE_PCT, MockSource

TODAY = date(2026, 10, 11)
START = TODAY - timedelta(days=365)


def make(live=0, today=TODAY):
    return MockSource(seed=42, start_date=START, today=today, live_count=live)


def history(src):
    return [t for t in src.fetch_transactions(None) if not t.external_id.startswith("live-")]


def test_deterministic():
    assert make(3).fetch_transactions(None) == make(3).fetch_transactions(None)
    assert make(3).list_accounts() == make(3).list_accounts()


def test_external_ids_unique():
    txns = make(5).fetch_transactions(None)
    assert len({t.external_id for t in txns}) == len(txns)


def test_history_window_ends_yesterday():
    rows = history(make())
    assert min(t.date for t in rows) >= START
    assert max(t.date for t in rows) == TODAY - timedelta(days=1)
    assert len(rows) > 1000


def test_live_drip_is_dated_today_and_stable_prefix():
    three = [t for t in make(3).fetch_transactions(None) if t.external_id.startswith("live-")]
    five = [t for t in make(5).fetch_transactions(None) if t.external_id.startswith("live-")]
    assert len(three) == 3 and len(five) == 5
    assert all(t.date == TODAY for t in five)
    assert five[:3] == three


def test_business_items_on_personal_card_have_hints():
    rows = [t for t in history(make()) if t.account_external_id == "visa"]
    prior = [t for t in rows if t.date < TODAY.replace(day=1) and t.hint_business_status]
    assert any("GITHUB" in t.description for t in prior)
    assert all(t.category_id for t in prior)
    current_github = [t for t in rows if t.date >= TODAY.replace(day=1) and "GITHUB" in t.description]
    assert current_github  # posts on the 5th


def test_reimbursement_equals_prior_month_business_share():
    src = make()
    rows = history(src)
    reimb = [
        t
        for t in rows
        if t.account_external_id == "joint-checking"
        and t.category_id == "accountable_plan_reimbursement"
        and t.date == date(2026, 10, 3)
    ]
    assert len(reimb) == 1
    september = [t for t in rows if t.date.year == 2026 and t.date.month == 9]
    expected = sum(-t.amount_cents for t in september if t.hint_business_status == "business")
    expected += sum(
        pct_of(-t.amount_cents, MIXED_USE_PCT)
        for t in september
        if any(k in t.description for k in ("VERIZON", "XFINITY"))
    )
    assert reimb[0].amount_cents == expected


def test_transfers_balance_between_accounts():
    rows = history(make())
    dist = [t for t in rows if t.category_id == "owner_distribution"]
    assert sum(t.amount_cents for t in dist) == 0 and dist


def test_balances_land_on_targets():
    src = make()
    accounts = {a.external_id: a for a in src.list_accounts()}
    rows = history(src)
    checking = accounts["joint-checking"].opening_balance_cents + sum(
        t.amount_cents for t in rows if t.account_external_id == "joint-checking"
    )
    assert 15_000_00 < checking < 40_000_00
    visa = accounts["visa"].opening_balance_cents + sum(
        t.amount_cents for t in rows if t.account_external_id == "visa"
    )
    assert -15_000_00 < visa <= 0
    assert accounts["brokerage"].current_balance_cents > 100_000_00
