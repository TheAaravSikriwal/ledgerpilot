import { useState } from "react";
import { money, moneyCompact } from "../lib/format";
import type { Summary } from "../lib/types";

const SEGMENTS = [
  { key: "cash_cents", label: "Household cash", color: "var(--series-1)" },
  { key: "investments_cents", label: "Brokerage", color: "var(--series-2)" },
  { key: "retirement_cents", label: "Retirement", color: "var(--series-3)" },
  { key: "business_cents", label: "S-Corp", color: "var(--series-4)" },
] as const;

/** Assets as one stacked bar (2px surface gaps), card debt listed separately as a deduction. */
export function NetWorthBar({ breakdown }: { breakdown: Summary["net_worth_breakdown"] }) {
  const [hover, setHover] = useState<string | null>(null);
  const assets = SEGMENTS.map((s) => ({ ...s, value: Math.max(0, breakdown[s.key]) }));
  const total = assets.reduce((sum, s) => sum + s.value, 0) || 1;
  const active = assets.find((s) => s.key === hover);

  return (
    <div>
      <div className="relative">
        <div className="flex h-3 w-full gap-[2px]" onMouseLeave={() => setHover(null)}>
          {assets.map((s, i) => (
            <div
              key={s.key}
              className="h-full cursor-default transition-opacity"
              style={{
                width: `${(s.value / total) * 100}%`,
                background: s.color,
                borderRadius:
                  i === 0 ? "4px 0 0 4px" : i === assets.length - 1 ? "0 4px 4px 0" : undefined,
                opacity: hover && hover !== s.key ? 0.45 : 1,
              }}
              onMouseEnter={() => setHover(s.key)}
              aria-label={`${s.label}: ${money(s.value)}`}
            />
          ))}
        </div>
        {active && (
          <div className="pointer-events-none absolute -top-12 left-1/2 -translate-x-1/2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs whitespace-nowrap shadow-card">
            <span className="text-ink-2">{active.label}</span>{" "}
            <span className="num font-medium text-ink">{money(active.value)}</span>{" "}
            <span className="text-muted">· {Math.round((active.value / total) * 100)}%</span>
          </div>
        )}
      </div>
      <ul className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2.5">
        {assets.map((s) => (
          <li
            key={s.key}
            className="flex items-center justify-between gap-2 text-sm"
            onMouseEnter={() => setHover(s.key)}
            onMouseLeave={() => setHover(null)}
          >
            <span className="flex min-w-0 items-center gap-2 text-ink-2">
              <span className="h-2.5 w-2.5 shrink-0 rounded-[3px]" style={{ background: s.color }} aria-hidden />
              <span className="truncate">{s.label}</span>
            </span>
            <span className="num text-ink">{moneyCompact(s.value)}</span>
          </li>
        ))}
        <li className="col-span-2 mt-1 flex items-center justify-between border-t border-line pt-2.5 text-sm">
          <span className="text-ink-2">Credit cards owed</span>
          <span className="num text-ink">−{moneyCompact(-breakdown.credit_cents)}</span>
        </li>
      </ul>
    </div>
  );
}
