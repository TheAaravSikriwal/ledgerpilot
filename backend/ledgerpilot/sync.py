"""Sync engine: fetch from sources → upsert/dedupe → categorize → reimbursements → publish."""

import logging
import threading
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from .business import match_reimbursements
from .categorize.rules import categorize
from .events import EventBus
from .models import Account, Category, Rule, SyncRun, Transaction
from .settings_store import get_setting
from .sources.base import Source, TransactionData, normalize_merchant

log = logging.getLogger(__name__)

MAX_NEW_IDS = 200

SourceFactory = Callable[[Session], Sequence[Source]]


def run_to_dict(run: SyncRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "source": run.source,
        "trigger": run.trigger,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "status": run.status,
        "new_count": run.new_count,
        "new_ids": run.new_ids or [],
        "error": run.error,
    }


def ingest(
    session: Session,
    source_name: str,
    txns: Iterable[TransactionData],
    resolve_account: Callable[[TransactionData], Account],
    ai_categorizer: Any = None,
) -> list[Transaction]:
    """Insert transactions not seen before (by source + external_id) and categorize them."""
    seen = set(
        session.scalars(
            select(Transaction.external_id).where(Transaction.source == source_name)
        ).all()
    )
    rules = list(session.scalars(select(Rule)).all())
    categories = {c.id: c for c in session.scalars(select(Category)).all()}
    mixed_pct = get_setting(session, "phone_internet_business_pct")
    now = datetime.now()

    created: list[Transaction] = []
    for data in txns:
        if data.external_id in seen:
            continue
        seen.add(data.external_id)
        account = resolve_account(data)
        merchant = data.merchant or normalize_merchant(data.description)
        result = categorize(
            text=f"{data.description} {merchant}",
            owner=account.owner,
            amount_cents=data.amount_cents,
            rules=rules,
            categories=categories,
            mixed_use_pct=mixed_pct,
            source_category_id=data.category_id,
            hint_status=data.hint_business_status,
            hint_pct=data.hint_business_pct,
        )
        txn = Transaction(
            account_id=account.id,
            source=source_name,
            external_id=data.external_id,
            date=data.date,
            description=data.description,
            merchant=merchant,
            amount_cents=data.amount_cents,
            category_id=result.category_id,
            categorized_by=result.categorized_by,
            rule_id=result.rule_id,
            business_status=result.business_status,
            business_pct=result.business_pct,
            created_at=now,
        )
        txn.account = account
        session.add(txn)
        created.append(txn)
    session.flush()

    if ai_categorizer is not None and get_setting(session, "ai_enabled"):
        pending = [t for t in created if t.category_id == "uncategorized"]
        if pending:
            ai_categorizer.apply(session, pending, categories, mixed_pct)
    return created


def recompute_balances(session: Session, accounts: Iterable[Account]) -> None:
    sums = dict(
        session.execute(
            select(Transaction.account_id, func.sum(Transaction.amount_cents)).group_by(
                Transaction.account_id
            )
        ).all()
    )
    for account in accounts:
        if account.type in ("brokerage", "401k", "ira_roth", "ira_traditional"):
            continue  # balance comes from the source
        account.balance_cents = account.opening_balance_cents + (sums.get(account.id) or 0)


class SyncEngine:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        source_factory: SourceFactory,
        bus: EventBus | None = None,
        ai_categorizer: Any = None,
    ) -> None:
        self.session_factory = session_factory
        self.source_factory = source_factory
        self.bus = bus
        self.ai_categorizer = ai_categorizer
        self.lock = threading.Lock()  # also held by demo reset

    def run(self, trigger: str = "manual") -> dict[str, Any]:
        with self.lock, self.session_factory() as session:
            run = SyncRun(source="", trigger=trigger, started_at=datetime.now(), status="running")
            session.add(run)
            session.commit()
            run_id = run.id
            try:
                sources = self.source_factory(session)
                run.source = ",".join(s.name for s in sources) or "none"
                new_ids: list[int] = []
                for source in sources:
                    new_ids += [t.id for t in self._sync_source(session, source)]
                match_reimbursements(session)
                run.status, run.new_count, run.new_ids = "ok", len(new_ids), new_ids[-MAX_NEW_IDS:]
                session.commit()
            except Exception as exc:  # a failed sync must never lose existing data
                log.exception("sync failed")
                session.rollback()
                run = session.get(SyncRun, run_id)
                run.status, run.error = "error", f"{type(exc).__name__}: {exc}"
            run.finished_at = datetime.now()
            session.commit()
            result = run_to_dict(run)
        if self.bus is not None:
            self.bus.publish("sync", result)
        return result

    def _sync_source(self, session: Session, source: Source) -> list[Transaction]:
        by_ext = {
            a.external_id: a
            for a in session.scalars(select(Account).where(Account.source == source.name)).all()
        }
        now = datetime.now()
        for data in source.list_accounts():
            account = by_ext.get(data.external_id)
            if account is None:
                account = Account(
                    source=source.name,
                    external_id=data.external_id,
                    owner=data.owner,
                    opening_balance_cents=data.opening_balance_cents or 0,
                )
                session.add(account)
                by_ext[data.external_id] = account
            account.name, account.institution, account.type = (
                data.name,
                data.institution,
                data.type,
            )
            if data.current_balance_cents is not None:
                account.balance_cents = data.current_balance_cents
            account.updated_at = now
        session.flush()

        created = ingest(
            session,
            source.name,
            source.fetch_transactions(None),
            lambda d: by_ext[d.account_external_id],
            self.ai_categorizer,
        )
        recompute_balances(session, by_ext.values())
        return created
