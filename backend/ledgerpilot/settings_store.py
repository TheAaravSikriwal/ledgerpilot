"""Typed access to user-editable settings stored in the `settings` table."""

from typing import Any

from sqlalchemy.orm import Session

from .models import Setting

DEFAULTS: dict[str, Any] = {
    "ai_enabled": False,
    "sync_interval_minutes": 15,
    "self_name": "Alex",
    "spouse_name": "Jordan",
    "business_name": "Rivera Consulting LLC",
    "filing_status": "mfj",
    "phone_internet_business_pct": 40,
}

FILING_STATUSES = ("single", "mfj", "mfs", "hoh")


def get_settings(session: Session) -> dict[str, Any]:
    stored = {row.key: row.value for row in session.query(Setting).all()}
    return {key: stored.get(key, default) for key, default in DEFAULTS.items()}


def get_setting(session: Session, key: str) -> Any:
    row = session.get(Setting, key)
    return row.value if row is not None else DEFAULTS[key]


def put_settings(session: Session, values: dict[str, Any]) -> dict[str, Any]:
    for key, value in values.items():
        if key not in DEFAULTS:
            raise KeyError(key)
        row = session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
    session.commit()
    return get_settings(session)
