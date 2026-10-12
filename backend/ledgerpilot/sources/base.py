"""The connector contract every data source (mock, CSV, Plaid, SimpleFIN, ...) implements.

Sources normalize to LedgerPilot conventions: integer cents, negative = money out.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class AccountData:
    external_id: str
    name: str
    institution: str
    type: str
    owner: str
    # Balance before the first transaction this source returns (transactional accounts).
    opening_balance_cents: int | None = None
    # Authoritative current balance (accounts without transactions, e.g. retirement).
    current_balance_cents: int | None = None


@dataclass(frozen=True)
class TransactionData:
    external_id: str
    account_external_id: str
    date: date
    description: str
    amount_cents: int
    merchant: str | None = None
    category_id: str | None = None
    # Prior decisions a source may carry (e.g. a user's past confirmations in the mock).
    hint_business_status: str | None = None
    hint_business_pct: int | None = None


class Source(Protocol):
    name: str

    def list_accounts(self) -> list[AccountData]: ...

    def fetch_transactions(self, since: date | None) -> list[TransactionData]: ...


_NOISE = re.compile(r"[#*]|\b\d[\d\-./]*\b|\b(POS|ACH|DEBIT|CREDIT|PURCHASE|PMT)\b", re.I)


def normalize_merchant(description: str) -> str:
    """Best-effort merchant name from a raw bank description."""
    cleaned = _NOISE.sub(" ", description)
    words = [w for w in re.split(r"\s+", cleaned) if w]
    return " ".join(words[:3]).title() or description.strip()[:40]
