"""ORM models. Money columns are integer cents; negative amounts are money out."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# Account owners. Everything except "business" is household (personal) money.
PERSONAL_OWNERS = ("self", "spouse", "joint")
BUSINESS_OWNER = "business"

# Category groups that count against the household budget.
BUDGET_GROUPS = ("essential", "discretionary")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128))
    institution: Mapped[str] = mapped_column(String(128))
    type: Mapped[str] = mapped_column(String(32))
    owner: Mapped[str] = mapped_column(String(16))
    opening_balance_cents: Mapped[int] = mapped_column(default=0)
    balance_cents: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime)

    @property
    def is_personal(self) -> bool:
        return self.owner in PERSONAL_OWNERS


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    group: Mapped[str] = mapped_column(String(16))
    irs_line: Mapped[str | None] = mapped_column(String(8))
    irs_detail: Mapped[str | None] = mapped_column(String(64))
    deductible_pct: Mapped[int] = mapped_column(default=100)
    personal_fallback_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"))
    sort_order: Mapped[int] = mapped_column(default=0)


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(String(128))
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"))
    # "business" = definitely business, "review" = likely business, None = personal.
    business_status: Mapped[str | None] = mapped_column(String(16))
    business_pct: Mapped[int | None]
    # Restrict to "business" or "personal" accounts; None applies to both.
    account_scope: Mapped[str | None] = mapped_column(String(16))
    priority: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[str] = mapped_column(String(16), default="system")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("source", "external_id"),
        Index("ix_transactions_date", "date"),
        Index("ix_transactions_account", "account_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(128))
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(256))
    merchant: Mapped[str] = mapped_column(String(128))
    amount_cents: Mapped[int]
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"))
    categorized_by: Mapped[str] = mapped_column(String(16), default="fallback")
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("rules.id", ondelete="SET NULL"))
    ai_rationale: Mapped[str | None] = mapped_column(Text)
    business_status: Mapped[str] = mapped_column(String(16), default="personal")
    business_pct: Mapped[int] = mapped_column(default=0)
    # Expenses: None / "owed" / "reimbursed". Reimbursement transfers: "applied" once allocated.
    reimbursement_status: Mapped[str | None] = mapped_column(String(16))
    reimbursed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    user_locked: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    account: Mapped[Account] = relationship(lazy="joined")
    category: Mapped[Category] = relationship(lazy="joined")


class BudgetTarget(Base):
    __tablename__ = "budget_targets"

    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), primary_key=True)
    monthly_cents: Mapped[int]


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(64))
    trigger: Mapped[str] = mapped_column(String(16), default="manual")
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="running")
    new_count: Mapped[int] = mapped_column(default=0)
    new_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)


class MockState(Base):
    __tablename__ = "mock_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    seed: Mapped[int]
    start_date: Mapped[date] = mapped_column(Date)
    live_count: Mapped[int] = mapped_column(default=0)
