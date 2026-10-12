import clsx from "clsx";
import { Sparkles } from "lucide-react";
import { shortDate, signedMoney } from "../lib/format";
import { useLive } from "../lib/live";
import type { Txn } from "../lib/types";
import { BusinessPill } from "./ui";

export function Monogram({ txn }: { txn: Txn }) {
  const letter = (txn.merchant || txn.description).trim().charAt(0).toUpperCase();
  return (
    <span
      className={clsx(
        "grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-semibold",
        txn.owner === "business"
          ? "bg-accent-soft text-accent"
          : txn.amount_cents > 0
            ? "bg-brass-soft text-brass"
            : "bg-surface-2 text-ink-2",
      )}
      aria-hidden
    >
      {letter}
    </span>
  );
}

/** Compact recent-activity list; rows that just arrived from a sync glow briefly. */
export function TxnFeed({ items, today }: { items: Txn[]; today?: string }) {
  const { newIds } = useLive();
  return (
    <ul className="divide-y divide-line">
      {items.map((t) => (
        <li
          key={t.id}
          className={clsx(
            "flex items-center gap-3 px-5 py-3 sm:px-6",
            newIds.has(t.id) && "arrived",
          )}
        >
          <Monogram txn={t} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="truncate text-sm font-medium text-ink">{t.merchant}</p>
              {newIds.has(t.id) && (
                <span className="rounded-full bg-brass px-1.5 py-px text-[10px] font-semibold tracking-wide text-surface uppercase">
                  New
                </span>
              )}
            </div>
            <p className="truncate text-xs text-muted">
              {t.category_name}
              {t.categorized_by === "ai" && (
                <Sparkles size={11} className="ml-1 inline text-brass" aria-label="Categorized by AI" />
              )}{" "}
              · {t.account_name} · {shortDate(t.date, today)}
            </p>
          </div>
          {t.business_status !== "personal" && (
            <span className="hidden sm:inline">
              <BusinessPill status={t.business_status} pct={t.business_pct} />
            </span>
          )}
          <span
            className={clsx(
              "num w-28 shrink-0 text-right text-sm font-medium",
              t.amount_cents > 0 ? "text-good-ink" : "text-ink",
            )}
          >
            {signedMoney(t.amount_cents)}
          </span>
        </li>
      ))}
    </ul>
  );
}
