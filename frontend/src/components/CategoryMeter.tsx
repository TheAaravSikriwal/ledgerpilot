import clsx from "clsx";
import { moneyWhole } from "../lib/format";
import type { CategoryLine } from "../lib/types";
import { PaceBadge, paceFill } from "./ui";

/** One category's month: fill = spent / target, tick = where spending "should" be today. */
export function CategoryMeter({ line, showBadge = true }: { line: CategoryLine; showBadge?: boolean }) {
  const target = Math.max(line.target_cents, 1);
  const fill = Math.min(100, (Math.max(line.spent_cents, 0) / target) * 100);
  const tick = Math.min(100, (line.expected_by_today_cents / target) * 100);
  const remaining = line.target_cents - line.spent_cents;

  return (
    <div className="group">
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="truncate text-sm text-ink">{line.name}</span>
        <span className="num shrink-0 text-xs text-ink-2">
          <span className="text-ink">{moneyWhole(line.spent_cents)}</span> / {moneyWhole(line.target_cents)}
        </span>
      </div>
      <div
        className="relative h-2 rounded-full bg-surface-3"
        role="meter"
        aria-label={`${line.name}: ${moneyWhole(line.spent_cents)} of ${moneyWhole(line.target_cents)}`}
        aria-valuemin={0}
        aria-valuemax={line.target_cents}
        aria-valuenow={Math.max(0, line.spent_cents)}
      >
        <div
          className={clsx("absolute inset-y-0 left-0 rounded-full transition-[width] duration-700", paceFill[line.status])}
          style={{ width: `${fill}%` }}
        />
        {line.expected_by_today_cents > 0 && line.expected_by_today_cents < line.target_cents && (
          <div
            className="absolute -top-1 -bottom-1 w-0.5 rounded-full bg-ink/70"
            style={{ left: `calc(${tick}% - 1px)` }}
            title={`Expected by today: ${moneyWhole(line.expected_by_today_cents)}`}
          />
        )}
      </div>
      {showBadge && (
        <div className="mt-1.5 flex items-center justify-between">
          <PaceBadge status={line.status} />
          <span className="num text-xs text-muted">
            {remaining >= 0 ? `${moneyWhole(remaining)} left` : `${moneyWhole(-remaining)} over`}
          </span>
        </div>
      )}
    </div>
  );
}
