import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { moneyCompact, moneyWhole } from "../lib/format";
import type { Budget } from "../lib/types";

interface Point {
  day: number;
  spent: number | null;
  pace: number;
}

function monthShort(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", { month: "short" });
}

function PaceTooltip({
  active,
  payload,
  month,
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: unknown }>;
  month: string;
}) {
  const point = payload?.[0]?.payload as Point | undefined;
  if (!active || !point) return null;
  const diff = point.spent === null ? null : point.spent - point.pace;
  return (
    <div className="rounded-xl border border-line bg-surface px-3.5 py-2.5 text-xs shadow-card">
      <p className="mb-1.5 font-medium text-ink">
        {monthShort(month)} {point.day}
      </p>
      <div className="grid grid-cols-[auto_auto] gap-x-4 gap-y-1 num">
        {point.spent !== null && (
          <>
            <span className="flex items-center gap-1.5 text-ink-2">
              <span className="h-0.5 w-3 rounded bg-[var(--series-1)]" aria-hidden /> Spent
            </span>
            <span className="text-right text-ink">{moneyWhole(point.spent * 100)}</span>
          </>
        )}
        <span className="flex items-center gap-1.5 text-ink-2">
          <span className="h-0.5 w-3 rounded bg-ink-2" aria-hidden /> On-budget pace
        </span>
        <span className="text-right text-ink">{moneyWhole(point.pace * 100)}</span>
      </div>
      {diff !== null && (
        <p className="mt-1.5 text-ink-2">
          {diff > 0 ? `${moneyWhole(diff * 100)} ahead of pace` : `${moneyWhole(-diff * 100)} under pace`}
        </p>
      )}
    </div>
  );
}

/** Cumulative household spending this month vs. the pace that lands exactly on budget. */
export function PaceChart({ budget }: { budget: Budget }) {
  const data: Point[] = budget.daily.map((d) => ({
    day: d.day,
    spent: d.spent_cents === null ? null : d.spent_cents / 100,
    pace: d.pace_cents / 100,
  }));
  const todayDay = budget.days_remaining > 0 ? budget.days_in_month - budget.days_remaining + 1 : null;
  const last = budget.days_in_month;
  const ticks = [1, 8, 15, 22, last];

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-ink-2" aria-hidden>
        <span className="flex items-center gap-2">
          <span className="h-0.5 w-4 rounded bg-[var(--series-1)]" /> Spent so far
        </span>
        <span className="flex items-center gap-2">
          <span className="h-0.5 w-4 rounded bg-ink-2" /> On-budget pace
        </span>
      </div>
      <div className="h-[220px] w-full" role="img" aria-label="Cumulative spending versus on-budget pace for the month">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--line)" strokeWidth={1} />
            <XAxis
              dataKey="day"
              type="number"
              domain={[1, last]}
              ticks={ticks}
              tickFormatter={(d: number) => `${monthShort(budget.month)} ${d}`}
              tickLine={false}
              axisLine={{ stroke: "var(--line-strong)" }}
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              tickMargin={8}
            />
            <YAxis
              width={56}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              tickFormatter={(v: number) => moneyCompact(v * 100)}
              tickCount={5}
            />
            {todayDay && (
              <ReferenceLine x={todayDay} stroke="var(--line-strong)" strokeWidth={1} />
            )}
            <Tooltip
              cursor={{ stroke: "var(--ink-2)", strokeWidth: 1 }}
              content={(p) => <PaceTooltip active={p.active} payload={p.payload} month={budget.month} />}
            />
            <Line
              dataKey="pace"
              type="linear"
              stroke="var(--ink-2)"
              strokeWidth={2}
              dot={false}
              activeDot={false}
              isAnimationActive={false}
            />
            <Area
              dataKey="spent"
              type="monotone"
              stroke="var(--series-1)"
              strokeWidth={2}
              fill="var(--series-1)"
              fillOpacity={0.1}
              connectNulls={false}
              dot={false}
              activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2, fill: "var(--series-1)" }}
              isAnimationActive
              animationDuration={700}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
