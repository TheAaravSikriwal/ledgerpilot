"""Deterministic mock bank for demos: the fictional Rivera household and their S-Corp.

Every day of history is generated from `random.Random(f"{seed}:{date}")`, so the same seed
and date always produce the same transactions and IDs. Each sync bumps `live_count`, which
adds "live" transactions dated today. All institutions and people here are fictional.
"""

import calendar
import random
from dataclasses import dataclass
from datetime import date, timedelta

from ..money import pct_of
from .base import AccountData, TransactionData

MIXED_USE_PCT = 40  # matches the default phone_internet_business_pct setting
CURRENT_MONTH_CONFIRMED_SHARE = 0.35  # rest of this month's business items await review
MARKET_WINDOW_DAYS = 30


@dataclass(frozen=True)
class _Spec:
    key: str
    name: str
    institution: str
    type: str
    owner: str
    target_cents: int | None = None  # depository balance "today"
    value_cents: int | None = None  # investment value around today (moves with market)
    beta: float = 1.0


ACCOUNTS: list[_Spec] = [
    _Spec("joint-checking", "Everyday Checking", "Harbor Federal", "checking", "joint", 24_380_00),
    _Spec("joint-savings", "High-Yield Savings", "Harbor Federal", "savings", "joint", 58_240_00),
    _Spec("visa", "Summit Rewards Visa", "Summit Card Services", "credit_card", "self"),
    _Spec(
        "biz-checking",
        "Business Checking",
        "Keystone Business Bank",
        "checking",
        "business",
        46_150_00,
    ),
    _Spec(
        "biz-card", "Business Platinum Card", "Keystone Business Bank", "credit_card", "business"
    ),
    _Spec(
        "brokerage",
        "Individual Brokerage",
        "Meridian Investments",
        "brokerage",
        "self",
        value_cents=186_420_00,
        beta=1.0,
    ),
    _Spec(
        "401k-northwind",
        "Northwind Systems 401(k)",
        "Fairway Retirement",
        "401k",
        "self",
        value_cents=142_870_00,
        beta=0.9,
    ),
    _Spec(
        "roth-ira",
        "Roth IRA",
        "Meridian Investments",
        "ira_roth",
        "self",
        value_cents=61_240_00,
        beta=1.1,
    ),
    _Spec(
        "trad-ira",
        "Traditional IRA",
        "Meridian Investments",
        "ira_traditional",
        "spouse",
        value_cents=18_930_00,
        beta=0.8,
    ),
    _Spec(
        "401k-old",
        "Old Employer 401(k)",
        "Granite Benefits",
        "401k",
        "self",
        value_cents=54_310_00,
        beta=0.85,
    ),
]
CARD_AUTOPAY = {"visa": ("joint-checking", 25), "biz-card": ("biz-checking", 26)}
PERSONAL_ACCOUNTS = {"joint-checking", "joint-savings", "visa"}

# Rules the demo user "trained" earlier (seeded on demo reset as user rules).
DEMO_USER_RULES = [
    ("THE CAPITAL GRILLE", "business_meals", "review"),
    ("GIBSONS", "business_meals", "review"),
]

# (weight, account, description, merchant, min_cents, max_cents)
LIVE_POOL = [
    (10, "visa", "STARBUCKS STORE 08211", "Starbucks", 525, 940),
    (7, "visa", "SWEETGREEN BOSTON", "Sweetgreen", 1350, 1890),
    (7, "visa", "WHOLE FOODS MKT #10234", "Whole Foods", 2400, 11800),
    (7, "visa", "AMAZON MKTPL*2K4L1", "Amazon", 1200, 8900),
    (4, "visa", "SHELL OIL 57442", "Shell", 3800, 6200),
    (5, "visa", "UBER *TRIP", "Uber", 1400, 3600),
    (4, "visa", "TARGET 00012345", "Target", 2200, 7400),
    (3, "visa", "DOORDASH*TATTE", "DoorDash", 2600, 5400),
    (5, "visa", "THE CAPITAL GRILLE BOSTON", "The Capital Grille", 9500, 21000),
    (3, "visa", "STAPLES 00123", "Staples", 1800, 7400),
    (3, "visa", "SQ *BLUE BOTTLE COFFEE", "Blue Bottle Coffee", 450, 1200),
    (4, "biz-card", "AMAZON WEB SERVICES AWS.AMAZON.CO", "Amazon Web Services", 400, 2800),
    (2, "biz-card", "LINKEDIN ADS 7731", "LinkedIn Ads", 2500, 9000),
]


@dataclass(frozen=True)
class _Txn:
    account: str
    description: str
    merchant: str
    amount_cents: int
    category_id: str | None = None  # categories a bank feed would know (transfers, payments)
    business_category: str | None = None  # business cost on a personal account


def _shift_to_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _is_pay_day(d: date, day: int) -> bool:
    last = calendar.monthrange(d.year, d.month)[1]
    return d == _shift_to_weekday(date(d.year, d.month, min(day, last)))


def _prev_month(d: date) -> tuple[int, int]:
    return (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)


def _month_days(year: int, month: int) -> list[date]:
    return [date(year, month, n) for n in range(1, calendar.monthrange(year, month)[1] + 1)]


class MockSource:
    name = "mock"

    def __init__(self, seed: int, start_date: date, today: date, live_count: int):
        self.seed = seed
        self.start_date = start_date
        self.today = today
        self.live_count = live_count
        self._cache: dict[date, list[_Txn]] = {}

    # ---- public Source API -------------------------------------------------------------

    def list_accounts(self) -> list[AccountData]:
        history = self.fetch_transactions(None, include_live=False)
        totals: dict[str, int] = {}
        for t in history:
            totals[t.account_external_id] = totals.get(t.account_external_id, 0) + t.amount_cents
        market = self._market_factor()
        accounts = []
        for spec in ACCOUNTS:
            opening = current = None
            if spec.value_cents is not None:
                current = round(spec.value_cents * (1 + spec.beta * (market - 1)))
            else:
                target = spec.target_cents
                if target is None:  # credit card: balance is whatever is not yet paid off
                    target = self._card_outstanding(spec.key)
                opening = target - totals.get(spec.key, 0)
            accounts.append(
                AccountData(
                    spec.key, spec.name, spec.institution, spec.type, spec.owner, opening, current
                )
            )
        return accounts

    def fetch_transactions(
        self, since: date | None, include_live: bool = True
    ) -> list[TransactionData]:
        out: list[TransactionData] = []
        d = max(self.start_date, since) if since else self.start_date
        while d < self.today:
            out.extend(self._to_data(d, i, t) for i, t in enumerate(self._day(d)))
            d += timedelta(days=1)
        if include_live:
            out.extend(self._live(i) for i in range(self.live_count))
        return out

    # ---- conversion & hints --------------------------------------------------------------

    def _to_data(self, d: date, i: int, t: _Txn) -> TransactionData:
        ext = f"d{d:%Y%m%d}-{i:02d}"
        category, hint, hint_pct = t.category_id, None, None
        if t.business_category:
            # Earlier months: the user already confirmed these. This month: some are
            # confirmed, the rest wait in the review queue.
            confirmed = d < self.today.replace(day=1) or (
                random.Random(f"{self.seed}:hint:{ext}").random() < CURRENT_MONTH_CONFIRMED_SHARE
            )
            if confirmed:
                category, hint, hint_pct = t.business_category, "business", 100
        return TransactionData(
            ext, t.account, d, t.description, t.amount_cents, t.merchant, category, hint, hint_pct
        )

    def _live(self, i: int) -> TransactionData:
        rng = random.Random(f"{self.seed}:live:{i}")
        _, account, desc, merchant, lo, hi = rng.choices(LIVE_POOL, [p[0] for p in LIVE_POOL])[0]
        return TransactionData(
            f"live-{i:05d}", account, self.today, desc, -rng.randint(lo, hi), merchant
        )

    # ---- balances --------------------------------------------------------------------------

    def _charges(self, account: str, year: int, month: int) -> int:
        """Net card activity (excluding payments) for a month, limited to the history window."""
        total = 0
        for d in _month_days(year, month):
            if self.start_date <= d < self.today:
                total += sum(
                    t.amount_cents
                    for t in self._day(d)
                    if t.account == account and t.category_id != "card_payment"
                )
        return total

    def _card_outstanding(self, account: str) -> int:
        _, autopay_day = CARD_AUTOPAY[account]
        outstanding = self._charges(account, self.today.year, self.today.month)
        prev_year, prev_month = _prev_month(self.today)
        if self.today.day <= autopay_day:  # last month's statement not yet paid
            outstanding += self._charges(account, prev_year, prev_month)
        return outstanding

    def _market_factor(self) -> float:
        """Market move over the trailing 30 days (plus an intraday wiggle per sync)."""
        factor, d = 1.0, self.today - timedelta(days=MARKET_WINDOW_DAYS)
        while d <= self.today:
            if d.weekday() < 5:
                factor *= 1 + random.Random(f"{self.seed}:mkt:{d}").gauss(0.00035, 0.0075)
            d += timedelta(days=1)
        if self.live_count:
            rng = random.Random(f"{self.seed}:intraday:{self.today}:{self.live_count}")
            factor *= 1 + rng.gauss(0, 0.002)
        return factor

    # ---- the day generator -----------------------------------------------------------------

    def _day(self, d: date) -> list[_Txn]:
        if d in self._cache:
            return self._cache[d]
        rng = random.Random(f"{self.seed}:{d.isoformat()}")
        month_rng = random.Random(f"{self.seed}:{d.year}-{d.month}")
        out: list[_Txn] = []

        def add(account, description, merchant, cents, category=None, business=None):
            out.append(_Txn(account, description, merchant, cents, category, business))

        def maybe(p: float) -> bool:
            return rng.random() < p

        def amt(lo: float, hi: float) -> int:
            return -rng.randint(round(lo * 100), round(hi * 100))

        dom, weekday, m = d.day, d.weekday(), d.month
        last_day = calendar.monthrange(d.year, m)[1]

        # --- Income -----------------------------------------------------------------------
        if _is_pay_day(d, 15) or _is_pay_day(d, last_day):
            add("joint-checking", "NORTHWIND SYSTEMS PAYROLL PPD", "Northwind Systems", 4_682_40)
        if weekday == 4 and (d - date(2025, 1, 3)).days % 14 == 0:
            add("joint-checking", "LAKESIDE HEALTH PAYROLL PPD", "Lakeside Health", 2_214_75)
        if _is_pay_day(d, 28):
            add("biz-checking", "GUSTO WAGES 1234567", "Gusto", -6_000_00)
            add("biz-checking", "GUSTO TAX 1234567", "Gusto", -459_00)
            add("joint-checking", "RIVERA CONSULTING LLC PAYROLL", "Rivera Consulting", 4_410_62)
        if dom == last_day:
            add("joint-savings", "INTEREST PAYMENT", "Harbor Federal", rng.randint(11_500, 16_000))

        # --- S-Corp revenue ------------------------------------------------------------------
        if _is_pay_day(d, 10):
            add("biz-checking", "ACME LABS ACH PAYMENT", "Acme Labs", 8_500_00)
        if _is_pay_day(d, 22):
            add("biz-checking", "BLUEFIN ANALYTICS ACH PAYMENT", "Bluefin Analytics", 4_200_00)
        if _is_pay_day(d, 17) and month_rng.random() < 0.55:
            add(
                "biz-checking",
                "HARBORVIEW HEALTH ACH PAYMENT",
                "Harborview Health",
                month_rng.randint(3_000, 6_500) * 100,
            )

        # --- S-Corp expenses (business card / business checking) -----------------------------
        if dom == 1:
            add("biz-card", "GOOGLE *WORKSPACE RIVERACONS", "Google Workspace", -28_80)
            add("biz-card", "WEWORK MEMBERSHIP", "WeWork", -450_00)
        if dom == 3:
            add(
                "biz-card", "AMAZON WEB SERVICES AWS.AMAZON.CO", "Amazon Web Services", amt(38, 140)
            )
        if dom == 6:
            add("biz-card", "ANTHROPIC API USAGE", "Anthropic", amt(20, 85))
        if dom == 8:
            add("biz-card", "FIGMA MONTHLY", "Figma", -45_00)
        if dom == 10:
            add("biz-card", "HISCOX INSURANCE", "Hiscox", -72_50)
        if dom == 12:
            add("biz-checking", "STRIPE FEE PAYOUT", "Stripe", amt(22, 64))
        if dom == 14 and month_rng.random() < 0.6:
            add("biz-card", "LINKEDIN ADS 7731", "LinkedIn Ads", amt(150, 420))
        if dom == 19 and month_rng.random() < 0.4:
            add("biz-card", "UPWORK ESCROW CONTRACTOR", "Upwork", amt(800, 2100))
        if dom == 20 and m in (1, 4, 7, 10):
            add("biz-checking", "LEDGERWISE CPA LLC", "Ledgerwise CPA", -350_00)
        if m == 2 and dom == 15:
            add("biz-checking", "SECRETARY OF THE COMMONWEALTH ANNUAL RPT", "MA Secretary", -500_00)

        # --- Owner flows & quarterly items ----------------------------------------------------
        quarter_end = m in (3, 6, 9, 12) and _is_pay_day(d, last_day)
        if quarter_end:
            add(
                "biz-checking",
                "OWNER DISTRIBUTION - A RIVERA",
                "Rivera Consulting",
                -12_000_00,
                "owner_distribution",
            )
            add(
                "joint-checking",
                "RIVERA CONSULTING LLC DIST",
                "Rivera Consulting",
                12_000_00,
                "owner_distribution",
            )
            add("biz-checking", "SOLO 401K EMPLOYER CONTRIB", "Fairway Retirement", -1_500_00)
        if m in (1, 4, 6, 9) and _is_pay_day(d, 15):
            add("joint-checking", "IRS USATAXPYMT", "IRS", -4_200_00)
            add("joint-checking", "MA DOR EST TAX PMT", "MA DOR", -1_150_00)
        if dom == 3 and d > self.start_date:
            owed = self._month_reimbursable(*_prev_month(d))
            if owed:
                add(
                    "biz-checking",
                    "ACCOUNTABLE PLAN REIMB - A RIVERA",
                    "Rivera Consulting",
                    -owed,
                    "accountable_plan_reimbursement",
                )
                add(
                    "joint-checking",
                    "RIVERA CONSULTING LLC REIMB",
                    "Rivera Consulting",
                    owed,
                    "accountable_plan_reimbursement",
                )

        # --- Card autopay (pays last month's statement) ---------------------------------------
        for card, (payer, autopay_day) in CARD_AUTOPAY.items():
            if _is_pay_day(d, autopay_day):
                charges = self._charges(card, *_prev_month(d))
                if charges < 0:
                    add(
                        payer,
                        f"{card.upper().replace('-', ' ')} AUTOPAY",
                        "Card payment",
                        charges,
                        "card_payment",
                    )
                    add(
                        card,
                        "AUTOPAY PAYMENT - THANK YOU",
                        "Card payment",
                        -charges,
                        "card_payment",
                    )

        # --- Household recurring --------------------------------------------------------------
        if dom == 1:
            add("joint-checking", "AVALONBAY COMMUNITIES RENT", "AvalonBay", -3_150_00)
            add(
                "joint-checking",
                "ONLINE TRANSFER TO SAVINGS",
                "Transfer",
                -1_500_00,
                "savings_transfer",
            )
            add(
                "joint-savings",
                "ONLINE TRANSFER FROM CHECKING",
                "Transfer",
                1_500_00,
                "savings_transfer",
            )
        if dom == 2:
            add("visa", "LEMONADE INSURANCE", "Lemonade", -18_00)
        if dom == 5:
            add(
                "joint-checking",
                "TRANSFER TO MERIDIAN INVESTMENTS",
                "Meridian Investments",
                -2_000_00,
                "savings_transfer",
            )
            add("visa", "GITHUB, INC.", "GitHub", -21_00, business="software_saas")
        if dom == 7:
            add("visa", "VERIZON WIRELESS PAYMENT", "Verizon", -142_18)
        if dom == 9:
            add("visa", "NETFLIX.COM", "Netflix", -22_99)
        if dom == 11:
            add("visa", "ADOBE *CREATIVE CLOUD", "Adobe", -59_99, business="software_saas")
        if dom == 12:
            add("joint-checking", "XFINITY INTERNET", "Xfinity", -89_99)
        if dom == 14:
            add("visa", "SPOTIFY USA", "Spotify", -19_99)
        if dom == 17:
            add("visa", "ZOOM.US 888-799-9666", "Zoom", -15_99, business="software_saas")
        if dom == 18:
            electric = 95 + (70 if m in (6, 7, 8) else 0) + (30 if m in (12, 1, 2) else 0)
            add(
                "joint-checking",
                "EVERSOURCE ENERGY",
                "Eversource",
                amt(electric - 15, electric + 25),
            )
        if dom == 20:
            add("visa", "GEICO AUTO", "Geico", -148_00)
        if dom == 21:
            gas = 40 + (150 if m in (12, 1, 2) else 0) + (80 if m in (11, 3) else 0)
            add("joint-checking", "NATIONAL GRID GAS", "National Grid", amt(gas - 10, gas + 30))
        if dom == 22:
            add("visa", "PLANET FITNESS", "Planet Fitness", -49_98)
        if dom == 23:
            add("visa", "NOTION LABS", "Notion", -10_00, business="software_saas")
        if dom == 3 and m in (2, 5, 8, 11):
            add("visa", "COURSERA.ORG", "Coursera", -49_00, business="education")

        # --- Business trips every other month (paid on the personal card) -----------------------
        if m % 2 == 0:
            if dom == 8:
                add("visa", "DELTA AIR LINES", "Delta", amt(380, 640), business="business_travel")
                add("visa", "UBER *TRIP", "Uber", amt(24, 48), business="business_travel")
            if dom == 9:
                add(
                    "visa",
                    "GIBSONS BAR & STEAKHOUSE",
                    "Gibsons",
                    amt(140, 260),
                    business="business_meals",
                )
            if dom == 10:
                add(
                    "visa",
                    "MARRIOTT CHICAGO",
                    "Marriott",
                    amt(450, 920),
                    business="business_travel",
                )
                add("visa", "UBER *TRIP", "Uber", amt(24, 48), business="business_travel")

        # --- Personal vacations -----------------------------------------------------------------
        if (m, dom) in ((3, 14), (7, 3), (12, 20)):
            add("visa", "JETBLUE AIRWAYS", "JetBlue", amt(420, 760))
        if (m, dom) in ((3, 15), (7, 4), (12, 21)):
            add("visa", "AIRBNB * HMQ2", "Airbnb", amt(950, 1600))

        # --- Everyday spending -----------------------------------------------------------------
        if maybe(0.4):
            store = rng.random()
            if store < 0.4:
                add("visa", "WHOLE FOODS MKT #10234", "Whole Foods", amt(45, 165))
            elif store < 0.75:
                add("visa", "TRADER JOE'S #512", "Trader Joe's", amt(35, 110))
            else:
                add("visa", "STAR MARKET 3561", "Star Market", amt(25, 90))
        if weekday == 5 and dom <= 7:
            add("joint-checking", "COSTCO WHSE #0318", "Costco", amt(180, 320))
        if maybe(0.3):
            add("visa", "STARBUCKS STORE 08211", "Starbucks", amt(5.25, 9.40))
        if weekday < 5 and maybe(0.15):
            add("visa", "SWEETGREEN BOSTON", "Sweetgreen", amt(13.5, 18.9))
        if maybe(0.06):
            add("visa", "CHIPOTLE 1123", "Chipotle", amt(11, 16))
        if maybe(0.12):
            add("visa", "DOORDASH*DINNER", "DoorDash", amt(26, 58))
        if maybe(0.07):
            add("visa", "TATTE BAKERY", "Tatte", amt(12, 24))
        if weekday in (4, 5) and maybe(0.3):
            add("visa", "OLEANA RESTAURANT", "Oleana", amt(95, 175))
        if weekday < 5 and maybe(0.06):
            add(
                "visa",
                "THE CAPITAL GRILLE BOSTON",
                "The Capital Grille",
                amt(95, 260),
                business="business_meals",
            )
        if weekday == 0 and maybe(0.8):
            add("visa", "SHELL OIL 57442", "Shell", amt(38, 64))
        if maybe(0.1):
            add("visa", "MBTA CHARLIECARD", "MBTA", -2_40)
        if maybe(0.08):
            add("visa", "UBER *TRIP", "Uber", amt(14, 36))
        if maybe(0.03):
            add("visa", "LYFT *RIDE", "Lyft", amt(12, 30))
        if maybe(0.22):
            add("visa", "AMAZON MKTPL*2K4L1", "Amazon", amt(12, 140))
        if maybe(0.12):
            add("visa", "TARGET 00012345", "Target", amt(22, 95))
        if maybe(0.02):
            add("visa", rng.choice(["REI #87 BOSTON", "UNIQLO BOSTON"]), "Apparel", amt(40, 180))
        if maybe(0.07):
            add("visa", "CVS/PHARMACY #0442", "CVS", amt(9, 48))
        if maybe(0.02):
            add("visa", "ONE MEDICAL COPAY", "One Medical", amt(25, 60))
        if maybe(0.04):
            add("visa", "AMC THEATRES 2231", "AMC Theatres", amt(28, 42))
        if maybe(0.012):
            add("visa", "TICKETMASTER", "Ticketmaster", amt(85, 240))
        if maybe(0.03):
            add("visa", "SEPHORA 0412", "Sephora", amt(25, 90))
        if maybe(0.015):
            add("visa", "GOFUNDME DONATION", "GoFundMe", amt(25, 100))
        if maybe(0.03):
            add("visa", "STAPLES 00123", "Staples", amt(18, 95), business="office_supplies")
        if maybe(0.03):
            add("visa", "SQ *BLUE BOTTLE COFFEE", "Blue Bottle Coffee", amt(4.5, 12))
        if m == 12 and maybe(0.25):
            add("visa", "AMAZON MKTPL*HOLIDAY", "Amazon", amt(30, 180))

        self._cache[d] = out
        return out

    def _month_reimbursable(self, year: int, month: int) -> int:
        """What the S-Corp owes for a month: personal-card business items + mixed-use share."""
        total = 0
        for d in _month_days(year, month):
            if not (self.start_date <= d < self.today):
                continue
            for t in self._day(d):
                if t.account not in PERSONAL_ACCOUNTS or t.amount_cents >= 0:
                    continue
                if t.business_category:
                    total += -t.amount_cents
                elif "VERIZON" in t.description or "XFINITY" in t.description:
                    total += pct_of(-t.amount_cents, MIXED_USE_PCT)
        return total
