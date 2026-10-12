import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Briefcase, CalendarClock } from "lucide-react";
import { Link } from "react-router";
import { CategoryMeter } from "../components/CategoryMeter";
import { NetWorthBar } from "../components/NetWorthBar";
import { PaceChart } from "../components/PaceChart";
import { TxnFeed } from "../components/TxnFeed";
import { Card, CardHeader, ErrorNote, PaceBadge, PageHeader, Skeleton, paceFill } from "../components/ui";
import { api } from "../lib/api";
import { greeting, money, moneyCompact, moneyWhole, monthLabel } from "../lib/format";
import type { CategoryLine } from "../lib/types";
import { useCountUp } from "../lib/useCountUp";

const SEVERITY = { over: 0, running_hot: 1, on_track: 2 } as const;

function byAttention(a: CategoryLine, b: CategoryLine) {
  if (SEVERITY[a.status] !== SEVERITY[b.status]) return SEVERITY[a.status] - SEVERITY[b.status];
  return b.spent_cents / Math.max(b.target_cents, 1) - a.spent_cents / Math.max(a.target_cents, 1);
}

function HeroNumber({ cents }: { cents: number }) {
  const shown = Math.max(0, Math.round(useCountUp(cents)));
  const dollars = Math.floor(shown / 100);
  const fraction = String(shown % 100).padStart(2, "0");
  return (
    <p className="text-[64px] leading-none font-semibold tracking-[-0.035em] text-ink sm:text-[76px]">
      <span className="mr-1 align-top text-[0.45em] font-medium text-ink-2">$</span>
      {dollars.toLocaleString("en-US")}
      <span className="text-[0.42em] font-medium text-muted">.{fraction}</span>
    </p>
  );
}

export default function Dashboard() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const budget = useQuery({ queryKey: ["budget", "current"], queryFn: () => api.budget() });
  const recent = useQuery({
    queryKey: ["transactions", "recent"],
    queryFn: () => api.transactions({ limit: 8 }),
  });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  if (summary.error) return <ErrorNote error={summary.error} />;
  const s = summary.data;
  const b = budget.data;
  const left = b ? b.target_cents - b.spent_cents : 0;
  const today = s ? new Date(`${s.today}T12:00:00`) : new Date();

  return (
    <>
      <PageHeader
        title={`${greeting()}, ${settings.data?.self_name ?? "there"}`}
        subtitle={
          <>
            {today.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
            {b && <> · {monthLabel(b.month)} budget, {b.days_remaining} days to go</>}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* Hero: the one number to act on today */}
        <Card className="rise rise-1 overflow-hidden lg:col-span-5">
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-brass/0 via-brass/70 to-brass/0"
            aria-hidden
          />
          <div className="flex h-full flex-col px-6 pt-6 pb-5 sm:px-7">
            <p className="text-[11px] font-medium tracking-[0.14em] text-muted uppercase">
              Safe to spend today
            </p>
            <div className="mt-4 mb-2">
              {s ? <HeroNumber cents={s.safe_to_spend_today_cents} /> : <Skeleton className="h-16 w-56" />}
            </div>
            <p className="max-w-sm text-sm text-ink-2">
              {b ? (
                <>
                  {left >= 0 ? `${moneyWhole(left)} left` : `${moneyWhole(-left)} over`} of your{" "}
                  {moneyWhole(b.target_cents)} household budget, after setting aside{" "}
                  {moneyWhole(b.upcoming_bills_cents)} for bills still coming.
                </>
              ) : (
                " "
              )}
            </p>
            {b && (
              <div className="mt-6 mb-6">
                <div className="mb-1.5 flex justify-between text-xs text-ink-2">
                  <span>Month budget used</span>
                  <span className="num">{Math.round((b.spent_cents / Math.max(b.target_cents, 1)) * 100)}%</span>
                </div>
                <div className="relative h-2 rounded-full bg-surface-3" aria-hidden>
                  <div
                    className={`absolute inset-y-0 left-0 rounded-full transition-[width] duration-700 ${paceFill[b.status]}`}
                    style={{ width: `${Math.min(100, (b.spent_cents / Math.max(b.target_cents, 1)) * 100)}%` }}
                  />
                  <div
                    className="absolute -top-1 -bottom-1 w-0.5 rounded-full bg-ink/70"
                    style={{ left: `${Math.min(100, (b.expected_by_today_cents / Math.max(b.target_cents, 1)) * 100)}%` }}
                    title="Where spending would be if you were exactly on budget"
                  />
                </div>
              </div>
            )}
            <div className="mt-auto grid grid-cols-3 gap-4 border-t border-line pt-4">
              <div>
                <p className="text-xs text-muted">Spent</p>
                <p className="num mt-0.5 text-sm font-semibold text-ink">{b ? moneyWhole(b.spent_cents) : "—"}</p>
              </div>
              <div>
                <p className="text-xs text-muted">Expected by now</p>
                <p className="num mt-0.5 text-sm font-semibold text-ink">
                  {b ? moneyWhole(b.expected_by_today_cents) : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted">Pace</p>
                <div className="mt-0.5">{b && <PaceBadge status={b.status} />}</div>
              </div>
            </div>
          </div>
        </Card>

        <Card className="rise rise-2 lg:col-span-7">
          <CardHeader eyebrow="This month" title="Spending pace" />
          <div className="px-3 pt-3 pb-4 sm:px-5">
            {b ? <PaceChart budget={b} /> : <Skeleton className="m-3 h-[220px]" />}
          </div>
        </Card>

        <Card className="rise rise-3 lg:col-span-7">
          <CardHeader
            eyebrow="Needs attention first"
            title="Category budgets"
            action={
              <Link to="/budget" className="inline-flex items-center gap-1 text-sm text-accent hover:underline">
                Edit budget <ArrowRight size={14} />
              </Link>
            }
          />
          <div className="grid gap-x-8 gap-y-5 px-5 pt-5 pb-6 sm:grid-cols-2 sm:px-6">
            {b
              ? [...b.categories]
                  .filter((c) => c.target_cents > 0)
                  .sort(byAttention)
                  .slice(0, 10)
                  .map((line) => <CategoryMeter key={line.category_id} line={line} />)
              : Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-12" />)}
          </div>
        </Card>

        <div className="flex flex-col gap-5 lg:col-span-5">
          <Card className="rise rise-3">
            <CardHeader
              eyebrow={settings.data?.business_name ?? "S-Corp"}
              title="Accountable plan"
              action={<Briefcase size={18} className="text-muted" strokeWidth={1.5} />}
            />
            <div className="px-5 pt-3 pb-5 sm:px-6">
              <p className="text-xs text-muted">The S-Corp owes you</p>
              <p className="num mt-1 text-3xl font-semibold tracking-tight text-ink">
                {s ? money(s.business.owed_to_you_cents) : "—"}
              </p>
              <p className="mt-1 text-xs text-ink-2">
                Business costs you paid personally this month. Reimbursements clear them automatically.
              </p>
              <div className="mt-4 flex items-center justify-between gap-3 rounded-xl bg-surface-2 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-ink">
                    {s?.business.review_count ?? 0} possible deduction
                    {s?.business.review_count === 1 ? "" : "s"} to review
                  </p>
                  <p className="text-xs text-ink-2">
                    {s ? `${moneyCompact(s.business.ytd_deductions_cents)} deducted so far in ${s.today.slice(0, 4)}` : ""}
                  </p>
                </div>
                <Link
                  to="/business"
                  className="inline-flex h-8 shrink-0 items-center gap-1 rounded-full bg-brass px-3 text-sm font-medium text-surface hover:opacity-90"
                >
                  Review <ArrowRight size={14} />
                </Link>
              </div>
            </div>
          </Card>

          <Card className="rise rise-4">
            <CardHeader eyebrow="Household + S-Corp" title="Net worth" />
            <div className="px-5 pt-2 pb-5 sm:px-6">
              <p className="num mb-4 text-3xl font-semibold tracking-tight text-ink">
                {s ? moneyWhole(s.net_worth_cents) : "—"}
              </p>
              {s && <NetWorthBar breakdown={s.net_worth_breakdown} />}
            </div>
          </Card>
        </div>

        <Card className="rise rise-5 lg:col-span-12">
          <CardHeader
            eyebrow="Live"
            title="Latest activity"
            action={
              <Link to="/transactions" className="inline-flex items-center gap-1 text-sm text-accent hover:underline">
                All transactions <ArrowRight size={14} />
              </Link>
            }
          />
          <div className="mt-3 pb-2">
            {recent.data ? (
              <TxnFeed items={recent.data.items} today={s?.today} />
            ) : (
              <div className="space-y-3 px-6 py-4">
                {Array.from({ length: 5 }, (_, i) => (
                  <Skeleton key={i} className="h-10" />
                ))}
              </div>
            )}
          </div>
          {b && b.upcoming_bills.length > 0 && (
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line px-5 py-3.5 text-xs text-ink-2 sm:px-6">
              <span className="inline-flex items-center gap-1.5 font-medium text-ink">
                <CalendarClock size={14} strokeWidth={1.75} /> Coming up
              </span>
              {b.upcoming_bills.map((bill) => (
                <span key={bill.merchant} className="num">
                  {bill.merchant} · {monthLabel(b.month).split(" ")[0].slice(0, 3)} {bill.expected_day} ·{" "}
                  <span className="text-ink">{moneyWhole(bill.amount_cents)}</span>
                </span>
              ))}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
