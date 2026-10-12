"""Opt-in Claude categorization for transactions the rules could not place.

Privacy: only date, description, merchant, amount and whether it was paid from a personal or
business account are sent — never account names/numbers, balances or household names.
Any failure (network, rate limit, refusal, bad output) leaves the transaction uncategorized.
"""

import json
import logging
import os
from collections.abc import Mapping, Sequence
from typing import Any

import anthropic
from sqlalchemy.orm import Session

from ..models import BUSINESS_OWNER, Category, Transaction
from ..money import dollars
from .rules import resolve_business

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
BATCH_SIZE = 25

SYSTEM_PROMPT = (
    "You categorize bank and credit-card transactions for a household whose owner also runs a "
    "consulting S-Corp. For each transaction choose the single best category_id from the "
    "allowed list. Set likely_business to true when the charge looks like an ordinary business "
    "expense of a consulting firm (software, client meals, business travel, office supplies, "
    "professional services), even if it was paid from a personal account. Give a rationale of "
    "at most 15 words. Use 'uncategorized' when you genuinely cannot tell."
)


def _schema(category_ids: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "category_id": {"type": "string", "enum": list(category_ids)},
                        "likely_business": {"type": "boolean"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["id", "category_id", "likely_business", "rationale"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["results"],
        "additionalProperties": False,
    }


def build_payload(txns: Sequence[Transaction]) -> list[dict[str, Any]]:
    return [
        {
            "id": t.id,
            "date": t.date.isoformat(),
            "description": t.description,
            "merchant": t.merchant,
            "amount": dollars(t.amount_cents),
            "paid_from": "business" if t.account.owner == BUSINESS_OWNER else "personal",
        }
        for t in txns
    ]


class AICategorizer:
    def __init__(self, api_key: str | None = None, model: str | None = None, client: Any = None):
        self.model = model or os.environ.get("LEDGERPILOT_AI_MODEL") or DEFAULT_MODEL
        self._client = client or anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=2)

    def classify(
        self, payload: list[dict[str, Any]], categories: Sequence[Category]
    ) -> dict[int, dict[str, Any]]:
        ids = [c.id for c in categories]
        response = self._client.beta.messages.create(
            model=self.model,
            max_tokens=8000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": _schema(ids)},
            },
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": "Allowed categories:\n"
                    + "\n".join(f"- {c.id}: {c.name} ({c.group})" for c in categories)
                    + "\n\nTransactions:\n"
                    + json.dumps(payload),
                }
            ],
        )
        if response.stop_reason == "refusal":
            log.warning("AI categorization declined (%s)", getattr(response, "stop_details", None))
            return {}
        text = next(b.text for b in response.content if b.type == "text")
        valid = set(ids)
        return {r["id"]: r for r in json.loads(text)["results"] if r.get("category_id") in valid}

    def apply(
        self,
        session: Session,
        txns: Sequence[Transaction],
        categories: Mapping[str, Category],
        mixed_use_pct: int,
    ) -> int:
        """Categorize `txns` in place. Returns how many were updated."""
        updated = 0
        for start in range(0, len(txns), BATCH_SIZE):
            batch = list(txns[start : start + BATCH_SIZE])
            try:
                results = self.classify(build_payload(batch), list(categories.values()))
            except anthropic.RateLimitError:
                log.warning("AI categorization rate-limited; leaving items uncategorized")
                break
            except anthropic.APIStatusError as exc:
                log.warning("AI categorization failed: HTTP %s", exc.status_code)
                break
            except anthropic.APIConnectionError:
                log.warning("AI categorization unreachable; leaving items uncategorized")
                break
            except (json.JSONDecodeError, StopIteration, KeyError, TypeError):
                log.warning("AI categorization returned unusable output")
                continue
            for t in batch:
                r = results.get(t.id)
                if not r or r["category_id"] == "uncategorized":
                    continue
                category_id, status, pct = resolve_business(
                    categories[r["category_id"]],
                    t.account.owner,
                    t.amount_cents,
                    "review" if r["likely_business"] else None,
                    None,
                    mixed_use_pct,
                )
                t.category_id, t.business_status, t.business_pct = category_id, status, pct
                t.categorized_by = "ai"
                t.ai_rationale = str(r.get("rationale", ""))[:300]
                updated += 1
        session.flush()
        return updated
