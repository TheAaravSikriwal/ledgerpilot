from datetime import date

import pytest
from sqlalchemy import func, select

from ledgerpilot.db import make_engine, make_session_factory
from ledgerpilot.demo import mock_source_factory, reset_demo
from ledgerpilot.main import migrate
from ledgerpilot.models import Account, SyncRun, Transaction
from ledgerpilot.sync import SyncEngine

TODAY = date(2026, 10, 11)


@pytest.fixture
def factory(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'sync.db').as_posix()}")
    migrate(engine)
    session_factory = make_session_factory(engine)
    reset_demo(session_factory, 42, TODAY)
    yield session_factory
    engine.dispose()


def count(session_factory, model=Transaction):
    with session_factory() as s:
        return s.scalar(select(func.count()).select_from(model))


def test_first_sync_loads_history_and_balances(factory):
    run = SyncEngine(factory, mock_source_factory(lambda: TODAY)).run("reset")
    assert run["status"] == "ok"
    assert count(factory) > 1000
    with factory() as s:
        checking = s.scalar(select(Account).where(Account.external_id == "joint-checking"))
        assert checking.balance_cents == 24_380_00  # live drip never touches checking
        brokerage = s.scalar(select(Account).where(Account.external_id == "brokerage"))
        assert brokerage.balance_cents > 100_000_00


def test_second_sync_adds_only_live_items(factory):
    engine = SyncEngine(factory, mock_source_factory(lambda: TODAY))
    engine.run("reset")
    before = count(factory)
    run = engine.run("manual")
    assert 1 <= run["new_count"] <= 4
    assert count(factory) == before + run["new_count"]
    with factory() as s:
        new = s.scalars(select(Transaction).where(Transaction.id.in_(run["new_ids"]))).all()
        assert all(t.date == TODAY for t in new)


def test_user_edits_survive_resync(factory):
    engine = SyncEngine(factory, mock_source_factory(lambda: TODAY))
    engine.run("reset")
    with factory() as s:
        t = s.scalars(select(Transaction).where(Transaction.merchant == "Target")).first()
        t.category_id, t.user_locked = "gifts", True
        s.commit()
        tid = t.id
    engine.run("manual")
    with factory() as s:
        assert s.get(Transaction, tid).category_id == "gifts"


def test_reimbursements_clear_prior_months(factory):
    SyncEngine(factory, mock_source_factory(lambda: TODAY)).run("reset")
    with factory() as s:
        owed = s.scalars(
            select(Transaction).where(Transaction.reimbursement_status == "owed")
        ).all()
        reimbursed = s.scalar(
            select(func.count()).where(Transaction.reimbursement_status == "reimbursed")
        )
        assert owed and reimbursed > 50
        assert all(t.date >= date(2026, 10, 1) for t in owed)
        review = s.scalar(select(func.count()).where(Transaction.business_status == "review"))
        assert review > 0


def test_failed_sync_is_recorded_without_data_loss(factory):
    SyncEngine(factory, mock_source_factory(lambda: TODAY)).run("reset")
    before = count(factory)

    def broken(_session):
        raise RuntimeError("bank is down")

    run = SyncEngine(factory, broken).run("manual")
    assert run["status"] == "error" and "bank is down" in run["error"]
    assert count(factory) == before
    assert count(factory, SyncRun) == 2
