import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Check, ChevronDown, Download, Info, X } from "lucide-react";
import { useState } from "react";
import { CategorySelect } from "../components/CategorySelect";
import { Monogram } from "../components/TxnFeed";
import { Button, Card, CardHeader, EmptyState, ErrorNote, PageHeader, Skeleton, Stat } from "../components/ui";
import { api } from "../lib/api";
import { money, moneyCompact, moneyWhole, shortDate } from "../lib/format";
import { useLive } from "../lib/live";
import type { BusinessSummary, Txn } from "../lib/types";
import { useUpdateTxn } from "../lib/useUpdateTxn";

function ReviewItem({ txn }: { txn: Txn }) {
  const update = useUpdateTxn();
  const { newIds } = useLive();
  const paidPersonally = txn.owner !== "business";
  return (
    <li className={clsx("flex flex-wrap items-center gap-x-4 gap-y-3 px-5 py-4 sm:px-6", newIds.has(txn.id) && "arrived")}>
      <Monogram txn={txn} />
      <div className="min-w-[180px] flex-1">
        <p className="font-medium text-ink">{txn.merchant}</p>
        <p className="text-xs text-muted">
          {shortDate(txn.date)} · {txn.account_name}
          {paidPersonally && <span className="text-brass"> · paid personally</span>}
        </p>
      </div>
      <CategorySelect
        value={txn.category_id}
        onChange={(id) => update.mutate({ id: txn.id, patch: { category_id: id } })}
        disabled={update.isPending}
      />
      <div className="w-36 text-right">
        <p className="num font-medium text-ink">{money(-txn.amount_cents)}</p>
        <p className="num text-xs text-good-ink">{money(txn.deductible_cents)} deductible</p>
      </div>
      <div className="flex gap-2">
        <Button
          variant="primary"
          className="h-8 px-3"
          icon={Check}
          disabled={update.isPending}
          onClick={() => update.mutate({ id: txn.id, patch: { business_status: "business" } })}
        >
          Business
        </Button>
        <Button
          variant="secondary"
          className="h-8 px-3"
          icon={X}
          disabled={update.isPending}
          onClick={() => update.mutate({ id: txn.id, patch: { business_status: "personal" } })}
        >
          Personal
        </Button>
      </div>
    </li>
  );
}

function DeductionBars({ summary }: { summary: BusinessSummary }) {
  const [open, setOpen] = useState<string | null>("20");
  const max = Math.max(...summary.lines.map((l) => l.amount_cents), 1);
  return (
    <ul className="space-y-1 px-3 pb-4 sm:px-4">
      {summary.lines.map((line) => {
        const expandable = line.details.length > 1;
        const isOpen = open === line.line && expandable;
        return (
          <li key={line.line}>
            <button
              type="button"
              disabled={!expandable}
              onClick={() => setOpen(isOpen ? null : line.line)}
              className={clsx(
                "grid w-full grid-cols-[3.5rem_minmax(0,1fr)] items-center gap-3 rounded-xl px-2 py-2.5 text-left sm:grid-cols-[3.5rem_16rem_minmax(0,1fr)]",
                expandable && "hover:bg-surface-2",
              )}
              aria-expanded={expandable ? isOpen : undefined}
            >
              <span className="num text-xs font-medium text-muted">Line {line.line}</span>
              <span className="flex items-center gap-1 truncate text-sm text-ink">
                {line.label}
                {expandable && (
                  <ChevronDown size={14} className={clsx("shrink-0 text-muted transition-transform", isOpen && "rotate-180")} />
                )}
              </span>
              <span className="col-span-2 flex items-center gap-3 sm:col-span-1">
                <span className="h-3 flex-1">
                  <span
                    className="block h-full rounded-r-[4px] bg-[var(--series-1)] transition-[width] duration-700"
                    style={{ width: `${(line.amount_cents / max) * 100}%` }}
                  />
                </span>
                <span className="num w-20 shrink-0 text-right text-sm font-medium text-ink">
                  {moneyCompact(line.amount_cents)}
                </span>
              </span>
            </button>
            {isOpen && (
              <ul className="mb-2 ml-[4.25rem] grid gap-1.5 border-l border-line py-1 pl-4 sm:grid-cols-2">
                {line.details.map((d) => (
                  <li key={d.name} className="flex justify-between gap-3 text-xs">
                    <span className="text-ink-2">{d.name}</span>
                    <span className="num text-ink">{money(d.amount_cents)}</span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default function Business() {
  const summary = useQuery({ queryKey: ["business", "summary"], queryFn: () => api.businessSummary() });
  const review = useQuery({ queryKey: ["business", "review"], queryFn: api.businessReview });
  const reimb = useQuery({ queryKey: ["business", "reimbursements"], queryFn: api.reimbursements });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const s = summary.data;

  if (summary.error) return <ErrorNote error={summary.error} />;

  return (
    <>
      <PageHeader
        title={settings.data?.business_name ?? "S-Corp"}
        subtitle={`S-Corporation · Form 1120-S · tax year ${s?.year ?? ""}`}
        actions={
          <a
            href={api.exportUrl(s?.year)}
            download
            className="inline-flex h-9 items-center gap-2 rounded-full border border-line-strong bg-surface px-4 text-sm font-medium text-ink hover:bg-surface-2"
          >
            <Download size={16} strokeWidth={1.75} /> Export for CPA
          </a>
        }
      />

      <Card className="rise rise-1 mb-5">
        <div className="grid grid-cols-2 gap-6 px-6 py-5 md:grid-cols-4">
          <Stat label="Revenue, year to date" value={s ? moneyWhole(s.income_cents) : "—"} />
          <Stat label="Deductions, year to date" value={s ? moneyWhole(s.total_deductions_cents) : "—"} />
          <Stat label="S-Corp owes you" value={s ? money(s.owed_cents) : "—"} hint="Accountable plan" />
          <Stat
            label="Waiting for review"
            value={s ? s.review_count : "—"}
            hint={s?.review_count ? "Possible deductions" : "All caught up"}
          />
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-12">
        <Card className="rise rise-2 lg:col-span-12">
          <CardHeader
            eyebrow="Review queue"
            title="Is this a business expense?"
            action={
              <span className="hidden max-w-sm text-right text-xs text-ink-2 md:block">
                Until you confirm, these count against the household budget.
              </span>
            }
          />
          <div className="mt-3">
            {review.data ? (
              review.data.length ? (
                <ul className="divide-y divide-line border-t border-line">
                  {review.data.map((t) => (
                    <ReviewItem key={t.id} txn={t} />
                  ))}
                </ul>
              ) : (
                <EmptyState title="Nothing to review" body="New likely-business charges will show up here as they sync." />
              )
            ) : (
              <Skeleton className="m-6 h-24" />
            )}
          </div>
        </Card>

        <Card className="rise rise-3 lg:col-span-7">
          <CardHeader eyebrow="Year to date" title="Deductions by Form 1120-S line" />
          <div className="mt-3">{s ? <DeductionBars summary={s} /> : <Skeleton className="m-6 h-48" />}</div>
        </Card>

        <Card className="rise rise-4 lg:col-span-5">
          <CardHeader eyebrow="Accountable plan" title="Reimbursements" />
          <div className="px-5 pt-3 pb-5 sm:px-6">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-xs text-muted">Owed to you now</p>
                <p className="num text-3xl font-semibold tracking-tight text-ink">
                  {reimb.data ? money(reimb.data.owed_total_cents) : "—"}
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted">Reimbursed this year</p>
                <p className="num text-lg font-medium text-ink-2">
                  {reimb.data ? moneyWhole(reimb.data.reimbursed_total_cents) : "—"}
                </p>
              </div>
            </div>
            <ul className="mt-4 divide-y divide-line rounded-xl border border-line">
              {reimb.data?.owed.slice(0, 8).map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                  <span className="min-w-0">
                    <span className="block truncate text-ink">{t.merchant}</span>
                    <span className="text-xs text-muted">
                      {shortDate(t.date)} · {t.category_name}
                      {t.business_pct < 100 && ` · ${t.business_pct}% business`}
                    </span>
                  </span>
                  <span className="num shrink-0 text-ink">{money(t.reimbursable_cents)}</span>
                </li>
              ))}
              {reimb.data && reimb.data.owed.length === 0 && (
                <li className="px-4 py-3 text-sm text-ink-2">Nothing owed — you’re square.</li>
              )}
            </ul>
            <p className="mt-4 flex gap-2 text-xs leading-relaxed text-ink-2">
              <Info size={14} className="mt-0.5 shrink-0 text-muted" />
              Under an accountable plan the S-Corp repays business costs you paid personally; the
              repayment isn’t income to you and the company deducts the expense. LedgerPilot clears
              items automatically when the reimbursement transfer lands.
            </p>
          </div>
        </Card>
      </div>
    </>
  );
}
