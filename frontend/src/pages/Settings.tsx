import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Sparkles } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button, Card, CardHeader, ErrorNote, PageHeader, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import type { Settings as SettingsT } from "../lib/types";

function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid gap-2 py-4 sm:grid-cols-[15rem_minmax(0,1fr)] sm:items-center sm:gap-6">
      <div>
        <p className="text-sm font-medium text-ink">{label}</p>
        {hint && <p className="text-xs text-ink-2">{hint}</p>}
      </div>
      <div>{children}</div>
    </div>
  );
}

const input =
  "h-9 w-full max-w-sm rounded-lg border border-line bg-surface px-3 text-sm text-ink focus:border-brass";

export default function Settings() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const [draft, setDraft] = useState<Partial<SettingsT>>({});
  const [confirmReset, setConfirmReset] = useState(false);

  const save = useMutation({
    mutationFn: (values: Partial<SettingsT>) => api.updateSettings(values),
    onSuccess: () => {
      setDraft({});
      void queryClient.invalidateQueries();
    },
  });
  const reset = useMutation({
    mutationFn: api.resetDemo,
    onSuccess: () => {
      setConfirmReset(false);
      void queryClient.invalidateQueries();
    },
  });

  if (settings.error) return <ErrorNote error={settings.error} />;
  const s = settings.data;
  if (!s) return <Skeleton className="h-96" />;
  const v = { ...s, ...draft };
  const set = <K extends keyof SettingsT>(key: K, value: SettingsT[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const dirty = Object.keys(draft).length > 0;

  return (
    <>
      <PageHeader
        title="Settings"
        actions={
          <Button variant="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate(draft)}>
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
        }
      />
      {save.error && <ErrorNote error={save.error} />}

      <div className="grid grid-cols-1 gap-5">
        <Card className="rise rise-1">
          <CardHeader title="Household" />
          <div className="divide-y divide-line px-5 sm:px-6">
            <Field label="Your name">
              <input className={input} value={v.self_name} onChange={(e) => set("self_name", e.target.value)} />
            </Field>
            <Field label="Spouse">
              <input className={input} value={v.spouse_name} onChange={(e) => set("spouse_name", e.target.value)} />
            </Field>
            <Field label="Filing status" hint="Drives brackets and IRA limits in later phases.">
              <select className={input} value={v.filing_status} onChange={(e) => set("filing_status", e.target.value as SettingsT["filing_status"])}>
                <option value="mfj">Married filing jointly</option>
                <option value="single">Single</option>
                <option value="hoh">Head of household</option>
                <option value="mfs">Married filing separately</option>
              </select>
            </Field>
          </div>
        </Card>

        <Card className="rise rise-2">
          <CardHeader title="S-Corp" />
          <div className="divide-y divide-line px-5 sm:px-6">
            <Field label="Business name">
              <input className={input} value={v.business_name} onChange={(e) => set("business_name", e.target.value)} />
            </Field>
            <Field
              label="Phone & internet business use"
              hint="Share of personal phone and home internet the S-Corp reimburses and deducts."
            >
              <div className="flex max-w-sm items-center gap-3">
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={v.phone_internet_business_pct}
                  onChange={(e) => set("phone_internet_business_pct", Number(e.target.value))}
                  className="flex-1 accent-[var(--accent)]"
                  aria-label="Phone and internet business use percent"
                />
                <span className="num w-12 text-right text-sm font-medium text-ink">{v.phone_internet_business_pct}%</span>
              </div>
            </Field>
          </div>
        </Card>

        <Card className="rise rise-3">
          <CardHeader title="Sync & intelligence" />
          <div className="divide-y divide-line px-5 sm:px-6">
            <Field label="Sync every" hint="How often LedgerPilot checks your sources in the background.">
              <select className={input} value={v.sync_interval_minutes} onChange={(e) => set("sync_interval_minutes", Number(e.target.value))}>
                {[1, 5, 15, 30, 60, 240].map((m) => (
                  <option key={m} value={m}>
                    {m < 60 ? `${m} minute${m === 1 ? "" : "s"}` : `${m / 60} hour${m === 60 ? "" : "s"}`}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label="Claude categorization"
              hint={
                s.ai_available
                  ? "Sends merchant, description, amount and date of uncategorized items — never account numbers or balances."
                  : "Add ANTHROPIC_API_KEY to the .env file and restart to enable."
              }
            >
              <label className="inline-flex cursor-pointer items-center gap-3">
                <input
                  type="checkbox"
                  className="peer sr-only"
                  checked={v.ai_enabled}
                  disabled={!s.ai_available}
                  onChange={(e) => set("ai_enabled", e.target.checked)}
                />
                <span className="relative h-6 w-11 rounded-full bg-surface-3 transition-colors peer-checked:bg-accent peer-disabled:opacity-50 after:absolute after:top-0.5 after:left-0.5 after:h-5 after:w-5 after:rounded-full after:bg-surface after:shadow after:transition-transform peer-checked:after:translate-x-5" />
                <span className="flex items-center gap-1.5 text-sm text-ink">
                  <Sparkles size={15} className="text-brass" /> {v.ai_enabled ? "On" : "Off"}
                </span>
              </label>
            </Field>
          </div>
        </Card>

        <Card className="rise rise-4">
          <CardHeader title="Demo data" />
          <div className="flex flex-wrap items-center justify-between gap-4 px-5 pt-2 pb-5 sm:px-6">
            <p className="max-w-xl text-sm text-ink-2">
              Rebuild the fictional household from scratch: a fresh year of history, budgets back to defaults, and
              your edits and rules cleared.
            </p>
            {confirmReset ? (
              <div className="flex gap-2">
                <Button variant="danger" icon={RotateCcw} disabled={reset.isPending} onClick={() => reset.mutate()}>
                  {reset.isPending ? "Rebuilding…" : "Yes, reset everything"}
                </Button>
                <Button variant="ghost" onClick={() => setConfirmReset(false)}>
                  Cancel
                </Button>
              </div>
            ) : (
              <Button variant="secondary" icon={RotateCcw} onClick={() => setConfirmReset(true)}>
                Reset demo
              </Button>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}
