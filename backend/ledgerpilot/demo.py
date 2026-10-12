"""Demo mode: the mock source's persistent state, source factory and reset."""

import random
from collections.abc import Callable
from datetime import date, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from .models import Account, BudgetTarget, MockState, Rule, SyncRun, Transaction
from .seed import seed_reference_data
from .sources.base import Source
from .sources.mock import DEMO_USER_RULES, MockSource

HISTORY_DAYS = 365


def mock_source_factory(today: Callable[[], date] = date.today):
    """Each sync advances the mock's live counter by 1–4, so new transactions appear."""

    def factory(session: Session) -> list[Source]:
        state = session.get(MockState, 1)
        if state is None:
            return []
        bump = random.Random(f"{state.seed}:bump:{state.live_count}").randint(1, 4)
        state.live_count += bump
        return [MockSource(state.seed, state.start_date, today(), state.live_count)]

    return factory


def reset_demo(session_factory: sessionmaker[Session], seed: int, today: date) -> None:
    """Wipe all data and reinstall the demo household (does not run a sync)."""
    with session_factory() as session:
        session.execute(delete(Transaction))
        session.execute(delete(Account))
        session.execute(delete(SyncRun))
        session.execute(delete(MockState))
        session.execute(delete(Rule).where(Rule.created_by == "user"))
        session.execute(delete(BudgetTarget))
        session.commit()
        seed_reference_data(session)
        for pattern, category_id, status in DEMO_USER_RULES:
            session.add(
                Rule(
                    pattern=pattern,
                    category_id=category_id,
                    business_status=status,
                    priority=50,
                    created_by="user",
                )
            )
        session.add(MockState(id=1, seed=seed, start_date=today - timedelta(days=HISTORY_DAYS)))
        session.commit()
