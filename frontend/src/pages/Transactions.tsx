import { keepPreviousData, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Check, ChevronLeft, ChevronRight, Search, Sparkles, Wand2, X } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { CategorySelect, useCategories } from "../components/CategorySelect";
import { Monogram } from "../components/TxnFeed";
import { BusinessPill, Button, Card, EmptyState, ErrorNote, PageHeader } from "../components/ui";
import { api, type TxnFilters } from "../lib/api";
import { shortDate, signedMoney } from "../lib/format";
import { useLive } from "../lib/live";
import type { Txn } from "../lib/types";
import { useUpdateTxn } from "../lib/useUpdateTxn";

const PAGE = 50;

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return v;
}

function RulePrompt({
  txn,
  categoryName,
  onDone,
}: {
  txn: Txn;
  categoryName: string;
  onDone: () => void;
}) {
  const update = useUpdateTxn();
  return (
    <tr className="bg-brass-soft/60">
      <td colSpan={6} className="px-5 py-2.5">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Wand2 size={15} className="text-brass" aria-hidden />
          <span className="text-ink">
            Always categorize <strong className="font-semibold">{txn.merchant}</strong> as{" "}
            <strong className="font-semibold">{categoryName}</strong>?
          </span>
          <span className="text-xs text-ink-2">Applies to past and future transactions you haven’t edited.</span>
          <span className="ml-auto flex gap-2">
            <Button
              variant="primary"
              className="h-8"
              icon={Check}
              disabled={update.isPending}
              onClick={() =>
                update.mutate(
                  { id: txn.id, patch: { category_id: txn.category_id, create_rule: true } },
                  { onSuccess: onDone },
                )
              }
            >
              Make it a rule
            </Button>
            <Button variant="ghost" className="h-8" icon={X} onClick={onDone}>
              Just this one
            </Button>
          </span>
        </div>
      </td>
    </tr>
  );
}

function BusinessControl({ txn }: { txn: Txn }) {
  const update = useUpdateTxn();
  const set = (business_status: "business" | "personal") =>
    update.mutate({ id: txn.id, patch: { business_status } });
  if (txn.business_status === "review") {
    return (
      <div className="flex items-center gap-1.5">
        <BusinessPill status="review" />
        <button
          type="button"
          onClick={() => set("business")}
          className="grid h-6 w-6 place-items-center rounded-full border border-accent/30 text-accent hover:bg-accent-soft"
          title="Confirm as a business expense"
          aria-label={`Confirm ${txn.merchant} as business`}
        >
          <Check size={13} strokeWidth={2.25} />
        </button>
        <button
          type="button"
          onClick={() => set("personal")}
          className="grid h-6 w-6 place-items-center rounded-full border border-line-strong text-ink-2 hover:bg-surface-2"
          title="It was personal"
          aria-label={`Mark ${txn.merchant} as personal`}
        >
          <X size={13} strokeWidth={2.25} />
        </button>
      </div>
    );
  }
  if (txn.owner === "business" || txn.amount_cents > 0) {
    return txn.business_status === "personal" ? null : (
      <BusinessPill status={txn.business_status} pct={txn.business_pct} />
    );
  }
  return (
    <button
      type="button"
      onClick={() => set(txn.business_status === "business" ? "personal" : "business")}
      title={txn.business_status === "business" ? "Mark as personal" : "Mark as a business expense"}
      className="rounded-full transition-opacity hover:opacity-80"
    >
      <BusinessPill status={txn.business_status} pct={txn.business_pct} />
    </button>
  );
}

export default function Transactions() {
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("q") ?? "");
  const q = useDebounced(search);
  const [offset, setOffset] = useState(0);
  const [prompt, setPrompt] = useState<number | null>(null);
  const { newIds } = useLive();
  const categories = useCategories();
  const update = useUpdateTxn();

  const filters: TxnFilters = {
    q,
    owner: params.get("owner") ?? undefined,
    business_status: params.get("status") ?? undefined,
    category_id: params.get("category") ?? undefined,
    month: params.get("month") ?? undefined,
    limit: PAGE,
    offset,
  };
  const page = useQuery({
    queryKey: ["transactions", filters],
    queryFn: () => api.transactions(filters),
    placeholderData: keepPreviousData,
  });

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
    setOffset(0);
  };

  const categoryName = (id: string) => categories.data?.find((c) => c.id === id)?.name ?? id;
  const total = page.data?.total ?? 0;

  return (
    <>
      <PageHeader
        title="Transactions"
        subtitle="Every account, one ledger. Change a category and LedgerPilot can learn it as a rule."
      />

      <Card className="rise rise-1">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3 sm:px-5">
          <label className="relative min-w-[220px] flex-1">
            <Search size={15} className="absolute top-1/2 left-3 -translate-y-1/2 text-muted" aria-hidden />
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
              placeholder="Search merchant or description"
              aria-label="Search transactions"
              className="h-9 w-full rounded-full border border-line bg-surface pr-3 pl-9 text-sm text-ink placeholder:text-muted focus:border-brass"
            />
          </label>
          <select
            value={params.get("owner") ?? ""}
            onChange={(e) => setFilter("owner", e.target.value)}
            aria-label="Paid from"
            className="h-9 rounded-full border border-line bg-surface px-3 text-sm text-ink"
          >
            <option value="">All accounts</option>
            <option value="personal">Household</option>
            <option value="business">S-Corp</option>
          </select>
          <select
            value={params.get("status") ?? ""}
            onChange={(e) => setFilter("status", e.target.value)}
            aria-label="Business status"
            className="h-9 rounded-full border border-line bg-surface px-3 text-sm text-ink"
          >
            <option value="">Any status</option>
            <option value="review">Needs review</option>
            <option value="business">Business</option>
            <option value="personal">Personal</option>
          </select>
          <CategorySelect
            includeAll
            value={params.get("category") ?? ""}
            onChange={(id) => setFilter("category", id)}
            className="h-9 rounded-full px-3"
          />
          <input
            type="month"
            value={params.get("month") ?? ""}
            onChange={(e) => setFilter("month", e.target.value)}
            aria-label="Month"
            className="h-9 rounded-full border border-line bg-surface px-3 text-sm text-ink"
          />
        </div>

        {page.error ? (
          <ErrorNote error={page.error} />
        ) : page.data && page.data.items.length === 0 ? (
          <EmptyState title="Nothing matches" body="Try a different search or clear a filter." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  <th className="px-5 py-2.5 font-medium">Date</th>
                  <th className="px-3 py-2.5 font-medium">Merchant</th>
                  <th className="px-3 py-2.5 font-medium">Account</th>
                  <th className="px-3 py-2.5 font-medium">Category</th>
                  <th className="px-3 py-2.5 font-medium">Business</th>
                  <th className="px-5 py-2.5 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody className={clsx(page.isPlaceholderData && "opacity-60")}>
                {page.data?.items.map((t) => (
                  <Fragment key={t.id}>
                    <tr className={clsx("border-b border-line hover:bg-surface-2/60", newIds.has(t.id) && "arrived")}>
                      <td className="num px-5 py-2.5 whitespace-nowrap text-ink-2">{shortDate(t.date)}</td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-3">
                          <Monogram txn={t} />
                          <div className="min-w-0">
                            <p className="truncate font-medium text-ink">{t.merchant}</p>
                            <p className="max-w-[260px] truncate text-xs text-muted" title={t.description}>
                              {t.description}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap text-ink-2">{t.account_name}</td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-1.5">
                          <CategorySelect
                            value={t.category_id}
                            disabled={update.isPending}
                            onChange={(id) =>
                              update.mutate(
                                { id: t.id, patch: { category_id: id } },
                                { onSuccess: () => setPrompt(t.id) },
                              )
                            }
                          />
                          {t.categorized_by === "ai" && (
                            <span title={t.ai_rationale ?? "Categorized by Claude"}>
                              <Sparkles size={14} className="text-brass" aria-label="Categorized by AI" />
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        <BusinessControl txn={t} />
                      </td>
                      <td
                        className={clsx(
                          "num px-5 py-2.5 text-right font-medium whitespace-nowrap",
                          t.amount_cents > 0 ? "text-good-ink" : "text-ink",
                        )}
                      >
                        {signedMoney(t.amount_cents)}
                      </td>
                    </tr>
                    {prompt === t.id && (
                      <RulePrompt txn={t} categoryName={categoryName(t.category_id)} onDone={() => setPrompt(null)} />
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between px-5 py-3 text-xs text-ink-2">
          <span className="num">
            {total ? `${offset + 1}–${Math.min(offset + PAGE, total)} of ${total.toLocaleString()}` : ""}
          </span>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              className="h-8 px-3"
              icon={ChevronLeft}
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE))}
            >
              Newer
            </Button>
            <Button
              variant="ghost"
              className="h-8 px-3"
              disabled={offset + PAGE >= total}
              onClick={() => setOffset(offset + PAGE)}
            >
              Older <ChevronRight size={16} />
            </Button>
          </div>
        </div>
      </Card>
    </>
  );
}
