"""Statement CSV import. Columns: date, description, amount (header row required).

Amounts follow LedgerPilot's convention (negative = money out); "$1,234.56" and "(12.34)" are
accepted. Re-importing the same file is a no-op because external IDs are content hashes.
"""

import csv
import hashlib
import io
from collections import Counter
from datetime import date, datetime

from .base import TransactionData

REQUIRED = ("date", "description", "amount")
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")


class CSVImportError(ValueError):
    pass


def _parse_date(value: str) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise CSVImportError(f"unrecognized date: {value!r}")


def _parse_amount(value: str) -> int:
    raw = value.strip().replace("$", "").replace(",", "")
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()")
    try:
        cents = round(float(raw) * 100)
    except ValueError as exc:
        raise CSVImportError(f"unrecognized amount: {value!r}") from exc
    return -abs(cents) if negative else cents


def parse_csv(content: str, account_key: str) -> list[TransactionData]:
    reader = csv.DictReader(io.StringIO(content.lstrip("﻿")))
    headers = {(h or "").strip().lower(): h for h in reader.fieldnames or []}
    missing = [h for h in REQUIRED if h not in headers]
    if missing:
        raise CSVImportError(f"missing column(s): {', '.join(missing)}")

    seen: Counter[tuple] = Counter()
    rows: list[TransactionData] = []
    for line_no, row in enumerate(reader, start=2):
        if not any((v or "").strip() for v in row.values()):
            continue
        try:
            d = _parse_date(row[headers["date"]])
            amount = _parse_amount(row[headers["amount"]])
        except CSVImportError as exc:
            raise CSVImportError(f"line {line_no}: {exc}") from exc
        description = row[headers["description"]].strip()
        key = (d, description, amount)
        seen[key] += 1  # identical rows on the same day are distinct transactions
        digest = hashlib.sha1(
            f"{account_key}|{d}|{description}|{amount}|{seen[key]}".encode()
        ).hexdigest()
        category = row.get(headers["category"]) if "category" in headers else None
        rows.append(
            TransactionData(
                external_id=f"csv-{digest[:20]}",
                account_external_id=account_key,
                date=d,
                description=description,
                amount_cents=amount,
                category_id=(category or "").strip() or None,
            )
        )
    return rows
