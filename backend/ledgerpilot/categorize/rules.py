"""Rule-based categorization and business-status resolution.

Order: source category (+ hints) → rules (user rules first, then priority, then specificity)
→ fallback. Business status depends on who owns the account:

- Business accounts: business-relevant categories are `business`; anything that looks personal,
  or an unknown outflow, goes to `review` as "Other business expense".
- Personal accounts: business categories are `review` (likely business) unless a rule says
  `business`; mixed-use categories (phone & internet) take the configured business share.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..models import BUSINESS_OWNER, Category, Rule

PERSONAL_LOOKING_GROUPS = ("essential", "discretionary", "other")


@dataclass(frozen=True)
class Categorization:
    category_id: str
    categorized_by: str  # "source" | "rule" | "ai" | "fallback"
    rule_id: int | None
    business_status: str  # "business" | "review" | "personal"
    business_pct: int


def _scope(owner: str) -> str:
    return "business" if owner == BUSINESS_OWNER else "personal"


def match_rule(rules: Sequence[Rule], text: str, owner: str) -> Rule | None:
    haystack = f" {text.upper()} "
    scope = _scope(owner)
    ordered = sorted(
        rules, key=lambda r: (r.created_by != "user", -(r.priority or 0), -len(r.pattern))
    )
    for rule in ordered:
        if rule.account_scope and rule.account_scope != scope:
            continue
        if rule.pattern.upper() in haystack:
            return rule
    return None


def resolve_business(
    category: Category,
    owner: str,
    amount_cents: int,
    rule_status: str | None,
    rule_pct: int | None,
    mixed_use_pct: int,
) -> tuple[str, str, int]:
    """Return (category_id, business_status, business_pct) for a categorized transaction."""
    if owner == BUSINESS_OWNER:
        if category.group in PERSONAL_LOOKING_GROUPS and amount_cents < 0:
            return "business_other", "review", 100
        return category.id, "business", 100

    if category.group == "business":
        status = rule_status or "review"
        return category.id, status, rule_pct if rule_pct is not None else 100
    if category.irs_line and rule_status == "business":
        return category.id, "business", rule_pct if rule_pct is not None else mixed_use_pct
    return category.id, "personal", 0


def categorize(
    *,
    text: str,
    owner: str,
    amount_cents: int,
    rules: Sequence[Rule],
    categories: Mapping[str, Category],
    mixed_use_pct: int,
    source_category_id: str | None = None,
    hint_status: str | None = None,
    hint_pct: int | None = None,
) -> Categorization:
    rule: Rule | None = None
    if source_category_id and source_category_id in categories:
        category, by = categories[source_category_id], "source"
        rule_status = rule_pct = None
    else:
        rule = match_rule(rules, text, owner)
        if rule is not None:
            category, by = categories[rule.category_id], "rule"
            rule_status, rule_pct = rule.business_status, rule.business_pct
        elif owner == BUSINESS_OWNER:
            if amount_cents < 0:
                return Categorization("business_other", "fallback", None, "review", 100)
            return Categorization("business_income", "fallback", None, "business", 100)
        else:
            return Categorization("uncategorized", "fallback", None, "personal", 0)

    category_id, status, pct = resolve_business(
        category, owner, amount_cents, rule_status, rule_pct, mixed_use_pct
    )
    if hint_status is not None and owner != BUSINESS_OWNER:
        status = hint_status
        if hint_status == "personal":
            pct = 0
        elif hint_pct is not None:
            pct = hint_pct
        elif pct == 0:
            pct = 100
    return Categorization(category_id, by, rule.id if rule else None, status, pct)
