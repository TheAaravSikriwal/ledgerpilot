import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CreditCard, FileUp, LineChart, PiggyBank, Wallet, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { Button, Card, CardHeader, ErrorNote, PageHeader, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { money, moneyWhole, relativeTime } from "../lib/format";
import type { Account } from "../lib/types";

const GROUPS: { title: string; icon: LucideIcon; match: (a: Account) => boolean }[] = [
  { title: "Household cash", icon: Wallet, match: (a) => a.owner !== "business" && (a.type === "checking" || a.type === "savings") },
  { title: "Credit cards", icon: CreditCard, match: (a) => a.owner !== "business" && a.type === "credit_card" },
  { title: "S-Corp", icon: Building2, match: (a) => a.owner === "business" },
  { title: "Brokerage", icon: LineChart, match: (a) => a.type === "brokerage" },
  { title: "Retirement", icon: PiggyBank, match: (a) => ["401k", "ira_roth", "ira_traditional"].includes(a.type) },
];

const TYPE_LABEL: Record<Account["type"], string> = {
  checking: "Checking",
  savings: "Savings",
  credit_card: "Credit card",
  brokerage: "Taxable brokerage",
  ira_traditional: "Traditional IRA",
  ira_roth: "Roth IRA",
  "401k": "401(k)",
};

const OWNER_LABEL: Record<Account["owner"], string> = {
  self: "You",
  spouse: "Spouse",
  joint: "Joint",
  business: "S-Corp",
};

function CsvImport({ accounts }: { accounts: Account[] }) {
  const queryClient = useQueryClient();
  const [accountId, setAccountId] = useState<number | "">("");
  const [file, setFile] = useState<File | null>(null);
  const run = useMutation({
    mutationFn: () => api.importCsv(Number(accountId), file!),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  const transactional = accounts.filter((a) => ["checking", "savings", "credit_card"].includes(a.type));
  return (
    <Card className="rise rise-4">
      <CardHeader eyebrow="Bring your own statement" title="Import a CSV" />
      <div className="space-y-3 px-5 pt-3 pb-5 sm:px-6">
        <p className="text-sm text-ink-2">
          Columns <code className="rounded bg-surface-2 px-1 text-xs">date, description, amount</code> (money out
          is negative). Re-importing the same file never creates duplicates.
        </p>
        <div className="flex flex-wrap gap-2">
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : "")}
            aria-label="Import into account"
            className="h-9 rounded-full border border-line bg-surface px-3 text-sm text-ink"
          >
            <option value="">Choose account…</option>
            {transactional.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
          <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-full border border-dashed border-line-strong px-4 text-sm text-ink-2 hover:bg-surface-2">
            <FileUp size={15} strokeWidth={1.75} />
            <span className="max-w-48 truncate">{file ? file.name : "Choose CSV file"}</span>
            <input type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <Button variant="primary" disabled={!accountId || !file || run.isPending} onClick={() => run.mutate()}>
            {run.isPending ? "Importing…" : "Import"}
          </Button>
        </div>
        {run.data && (
          <p className="text-sm text-good-ink">
            Imported {run.data.imported} transaction{run.data.imported === 1 ? "" : "s"}
            {run.data.skipped ? `, skipped ${run.data.skipped} already in your ledger` : ""}.
          </p>
        )}
        {run.error && <p className="text-sm text-critical-ink">{(run.error as Error).message}</p>}
      </div>
    </Card>
  );
}

export default function Accounts() {
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.accounts });
  if (accounts.error) return <ErrorNote error={accounts.error} />;
  const list = accounts.data ?? [];
  const total = list.reduce((s, a) => s + a.balance_cents, 0);

  return (
    <>
      <PageHeader
        title="Accounts"
        subtitle={
          accounts.data ? `${list.length} accounts · ${moneyWhole(total)} net` : "Loading accounts…"
        }
      />
      <div className="grid gap-5 lg:grid-cols-2">
        {GROUPS.map((g, i) => {
          const rows = list.filter(g.match);
          if (accounts.data && rows.length === 0) return null;
          const sum = rows.reduce((s, a) => s + a.balance_cents, 0);
          return (
            <Card key={g.title} className={`rise rise-${Math.min(i + 1, 5)}`}>
              <CardHeader
                title={
                  <span className="flex items-center gap-2">
                    <g.icon size={17} strokeWidth={1.75} className="text-muted" /> {g.title}
                  </span>
                }
                action={<span className="num text-sm font-semibold text-ink">{accounts.data ? money(sum) : ""}</span>}
              />
              <ul className="mt-3 divide-y divide-line border-t border-line">
                {accounts.data
                  ? rows.map((a) => (
                      <li key={a.id} className="flex items-center justify-between gap-4 px-5 py-3 sm:px-6">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-ink">{a.name}</p>
                          <p className="text-xs text-muted">
                            {a.institution} · {TYPE_LABEL[a.type]} · {OWNER_LABEL[a.owner]}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="num text-sm font-medium text-ink">{money(a.balance_cents)}</p>
                          <p className="text-[11px] text-muted">
                            <span className="rounded-full bg-brass-soft px-1.5 py-px text-brass uppercase">{a.source}</span>{" "}
                            {relativeTime(a.updated_at)}
                          </p>
                        </div>
                      </li>
                    ))
                  : Array.from({ length: 2 }, (_, k) => <Skeleton key={k} className="mx-6 my-3 h-10" />)}
              </ul>
            </Card>
          );
        })}
        {accounts.data && <CsvImport accounts={list} />}
      </div>
    </>
  );
}
