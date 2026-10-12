import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { CategoryMeter } from "../components/CategoryMeter";
import { PaceChart } from "../components/PaceChart";
import { Button, Card, CardHeader, ErrorNote, PaceBadge, PageHeader, Skeleton, Stat } from "../components/ui";
import { api } from "../lib/api";
import { moneyWhole, monthLabel, shiftMonth } from "../lib/format";
import type { CategoryLine } from "../lib/types";

function TargetInput({ line, editable }: { line: CategoryLine; editable: boolean }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (cents: number) => api.setBudget(line.category_id, cents),
    onSuccess: () => queryClient.invalidateQueries(),
    onSettled: () => setDraft(null),
  });
  const value = draft ?? String(Math.round(line.target_cents / 100));
  const commit = () => {
    if (draft === null) return;
    const dollars = Number(draft);
    if (Number.isFinite(dollars) && dollars >= 0 && Math.round(dollars * 100) !== line.target_cents) {
      save.mutate(Math.round(dollars * 100));
    } else setDraft(null);
  };
  return (
    <label className="relative block w-28">
      <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-sm text-muted">$</span>
      <input
        type="number"
        min={0}
        step={10}
        inputMode="decimal"
        disabled={!editable || save.isPending}
        value={value}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        aria-label={`Monthly target for ${line.name}`}
        className="num h-9 w-full rounded-lg border border-line bg-surface pr-2 pl-6 text-right text-sm text-ink focus:border-brass disabled:opacity-60"
      />
    </label>
  );
}

export default function Budget() {
  const current = useQuery({ queryKey: ["budget", "current"], queryFn: () => api.budget() });
  const [month, setMonth] = useState<string | null>(null);
  const shown = month ?? current.data?.month;
  const budget = useQuery({
    queryKey: ["budget", shown],
    queryFn: () => api.budget(shown),
    enabled: !!shown,
  });
  const b = budget.data;
  const isCurrent = shown === current.data?.month;

  if (budget.error) return <ErrorNote error={budget.error} />;

  const groups: { title: string; key: string }[] = [
    { title: "Essentials", key: "essential" },
    { title: "Lifestyle", key: "discretionary" },
  ];

  return (
    <>
      <PageHeader
        title="Budget"
        subtitle="Monthly targets for household spending. S-Corp expenses never count here."
        actions={
          <div className="flex items-center gap-1 rounded-full border border-line bg-surface p-1">
            <Button variant="ghost" className="h-8 w-8 px-0" aria-label="Previous month" onClick={() => shown && setMonth(shiftMonth(shown, -1))}>
              <ChevronLeft size={16} />
            </Button>
            <span className="min-w-36 text-center text-sm font-medium text-ink">{shown ? monthLabel(shown) : "…"}</span>
            <Button
              variant="ghost"
              className="h-8 w-8 px-0"
              aria-label="Next month"
              disabled={isCurrent}
              onClick={() => shown && setMonth(shiftMonth(shown, 1))}
            >
              <ChevronRight size={16} />
            </Button>
          </div>
        }
      />

      <div className="grid gap-5 lg:grid-cols-12">
        <Card className="rise rise-1 lg:col-span-12">
          <div className="grid grid-cols-2 gap-6 px-6 py-5 md:grid-cols-5">
            <Stat label="Monthly budget" value={b ? moneyWhole(b.target_cents) : "—"} />
            <Stat label="Spent" value={b ? moneyWhole(b.spent_cents) : "—"} />
            <Stat
              label={isCurrent ? "Expected by today" : "Left over"}
              value={b ? moneyWhole(isCurrent ? b.expected_by_today_cents : b.target_cents - b.spent_cents) : "—"}
            />
            <Stat label="Safe to spend / day" value={b && isCurrent ? moneyWhole(b.safe_to_spend_today_cents) : "—"} hint={isCurrent && b ? `${b.days_remaining} days left` : "Month closed"} />
            <div>
              <p className="text-xs font-medium text-muted">Pace</p>
              <div className="mt-2">{b && <PaceBadge status={b.status} />}</div>
            </div>
          </div>
        </Card>

        <Card className="rise rise-2 lg:col-span-8">
          <CardHeader eyebrow={shown ? monthLabel(shown) : ""} title="Spending pace" />
          <div className="px-3 pt-3 pb-4 sm:px-5">{b ? <PaceChart budget={b} /> : <Skeleton className="m-3 h-[220px]" />}</div>
        </Card>

        <Card className="rise rise-3 lg:col-span-4">
          <CardHeader eyebrow="Detected from your history" title="Bills still coming" />
          <ul className="mt-3 divide-y divide-line px-5 pb-4 sm:px-6">
            {b?.upcoming_bills.map((bill) => (
              <li key={bill.merchant} className="flex items-center justify-between py-2.5 text-sm">
                <span className="flex items-center gap-2 text-ink">
                  <CalendarClock size={15} className="text-muted" strokeWidth={1.75} />
                  {bill.merchant}
                </span>
                <span className="num text-ink-2">
                  day {bill.expected_day} · <span className="text-ink">{moneyWhole(bill.amount_cents)}</span>
                </span>
              </li>
            ))}
            {b && b.upcoming_bills.length === 0 && (
              <li className="py-3 text-sm text-ink-2">{isCurrent ? "No more recurring bills expected this month." : "—"}</li>
            )}
          </ul>
        </Card>

        {groups.map((g, i) => (
          <Card key={g.key} className={`rise rise-${i + 3} lg:col-span-6`}>
            <CardHeader title={g.title} />
            <ul className="mt-2 divide-y divide-line">
              {b?.categories
                .filter((c) => c.group === g.key)
                .map((line) => (
                  <li key={line.category_id} className="flex items-center gap-5 px-5 py-3.5 sm:px-6">
                    <div className="min-w-0 flex-1">
                      <CategoryMeter line={line} />
                    </div>
                    <TargetInput line={line} editable={!!isCurrent} />
                  </li>
                ))}
            </ul>
          </Card>
        ))}
      </div>
    </>
  );
}
