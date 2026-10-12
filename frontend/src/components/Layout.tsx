import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  ArrowLeftRight,
  Briefcase,
  Landmark,
  LayoutDashboard,
  Monitor,
  Moon,
  RefreshCw,
  Settings as SettingsIcon,
  Sun,
  Target,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router";
import { api } from "../lib/api";
import { relativeTime } from "../lib/format";
import { useLive } from "../lib/live";
import { useTheme, type ThemeChoice } from "../lib/theme";

const NAV: { to: string; label: string; icon: LucideIcon; badge?: "review" }[] = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/transactions", label: "Transactions", icon: ArrowLeftRight },
  { to: "/business", label: "S-Corp", icon: Briefcase, badge: "review" },
  { to: "/budget", label: "Budget", icon: Target },
  { to: "/accounts", label: "Accounts", icon: Landmark },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="h-8 w-8 shrink-0" aria-hidden>
        <rect width="32" height="32" rx="9" fill="var(--accent)" />
        <circle cx="16" cy="16" r="9" fill="none" stroke="var(--brass)" strokeWidth="1.6" />
        <path d="M16 8.5 L18.4 16 L16 23.5 L13.6 16 Z" fill="var(--accent-ink)" />
      </svg>
      <span className="serif text-[26px] leading-none text-ink">
        Ledger<span className="italic text-brass">pilot</span>
      </span>
    </div>
  );
}

function SyncStatus() {
  const { connected, syncNow, syncing } = useLive();
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const [, tick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => tick((n) => n + 1), 30_000);
    return () => window.clearInterval(id);
  }, []);
  const last = summary.data?.last_sync;
  return (
    <div className="flex items-center gap-3">
      <span className="hidden items-center gap-2 text-xs text-ink-2 sm:inline-flex">
        <span
          className={clsx(
            "h-2 w-2 rounded-full",
            connected ? "live-dot bg-good" : "bg-muted",
          )}
          aria-hidden
        />
        {connected ? "Live" : "Reconnecting…"}
        {last?.finished_at && (
          <span className="text-muted">· synced {relativeTime(last.finished_at)}</span>
        )}
        {last?.status === "error" && <span className="text-critical-ink">· last sync failed</span>}
      </span>
      <button
        type="button"
        onClick={syncNow}
        disabled={syncing}
        className="inline-flex h-9 items-center gap-2 rounded-full bg-accent px-4 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-hover disabled:opacity-60"
      >
        <RefreshCw size={15} strokeWidth={2} className={clsx(syncing && "spin")} aria-hidden />
        {syncing ? "Syncing…" : "Sync now"}
      </button>
    </div>
  );
}

const THEMES: { value: ThemeChoice; icon: LucideIcon; label: string }[] = [
  { value: "light", icon: Sun, label: "Light theme" },
  { value: "system", icon: Monitor, label: "Match system" },
  { value: "dark", icon: Moon, label: "Dark theme" },
];

function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  return (
    <div className="flex rounded-full border border-line bg-surface p-0.5" role="radiogroup" aria-label="Theme">
      {THEMES.map((t) => (
        <button
          key={t.value}
          type="button"
          role="radio"
          aria-checked={theme === t.value}
          aria-label={t.label}
          title={t.label}
          onClick={() => setTheme(t.value)}
          className={clsx(
            "grid h-7 w-7 place-items-center rounded-full transition-colors",
            theme === t.value ? "bg-surface-3 text-ink" : "text-muted hover:text-ink",
          )}
        >
          <t.icon size={14} strokeWidth={1.75} aria-hidden />
        </button>
      ))}
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const reviewCount = summary.data?.business.review_count ?? 0;

  return (
    <div className="relative z-10 flex min-h-screen flex-col lg:flex-row">
      <aside className="border-b border-line bg-surface/70 backdrop-blur lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-64 lg:shrink-0 lg:flex-col lg:border-r lg:border-b-0">
        <div className="flex items-center justify-between px-4 py-4 lg:px-6 lg:py-7">
          <Wordmark />
          <div className="lg:hidden">
            <ThemeToggle />
          </div>
        </div>

        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 [scrollbar-width:none] lg:flex-col lg:px-4 lg:pb-0" aria-label="Main">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                clsx(
                  "group flex shrink-0 items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent-soft text-accent"
                    : "text-ink-2 hover:bg-surface-2 hover:text-ink",
                )
              }
            >
              <item.icon size={17} strokeWidth={1.75} aria-hidden />
              <span>{item.label}</span>
              {item.badge === "review" && reviewCount > 0 && (
                <span
                  className="ml-auto grid h-5 min-w-5 place-items-center rounded-full bg-brass px-1.5 text-[11px] font-semibold text-surface"
                  aria-label={`${reviewCount} to review`}
                >
                  {reviewCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto hidden px-6 pb-6 lg:block">
          <div className="rounded-xl border border-dashed border-line-strong p-4">
            <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-brass">
              Demo household
            </p>
            <p className="mt-1 text-sm text-ink">
              {settings.data
                ? `${settings.data.self_name} & ${settings.data.spouse_name}`
                : "Loading…"}
            </p>
            <p className="text-xs text-ink-2">{settings.data?.business_name ?? ""}</p>
            <p className="mt-3 text-xs leading-relaxed text-muted">
              Fictional data from the mock bank. Next up: tax-loss harvesting, then the IRA &
              Solo 401(k) planner.
            </p>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-end gap-3 border-b border-line bg-bg/80 px-4 py-3 backdrop-blur sm:px-8">
          <SyncStatus />
          <div className="hidden lg:block">
            <ThemeToggle />
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 py-6 sm:px-8 sm:py-8">
          {children}
        </main>
        <footer className="border-t border-line px-4 py-5 text-xs leading-relaxed text-muted sm:px-8">
          LedgerPilot runs entirely on this computer and is for information only. It is not tax,
          legal or investment advice — confirm deductions and retirement decisions with your CPA
          or a licensed financial planner.
        </footer>
      </div>
    </div>
  );
}
