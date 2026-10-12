import pytest

from ledgerpilot.models import Category, Rule
from ledgerpilot.seed import CATEGORIES, SYSTEM_RULES


@pytest.fixture
def categories() -> dict[str, Category]:
    return {
        cid: Category(
            id=cid,
            name=name,
            group=group,
            irs_line=line,
            irs_detail=detail,
            deductible_pct=pct,
            personal_fallback_id=fallback,
        )
        for cid, name, group, line, detail, pct, fallback in CATEGORIES
    }


@pytest.fixture
def system_rules() -> list[Rule]:
    return [
        Rule(
            id=i,
            pattern=pattern,
            category_id=cid,
            business_status=status,
            business_pct=pct,
            account_scope=scope,
            priority=priority,
            created_by="system",
        )
        for i, (pattern, cid, status, pct, scope, priority) in enumerate(SYSTEM_RULES, start=1)
    ]
