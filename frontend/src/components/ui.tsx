import clsx from "clsx";
import { AlertTriangle, CheckCircle2, CircleAlert, type LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { BusinessStatus, PaceStatus } from "../lib/types";

export function Card({
  children,
  className,
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article";
}) {
  return (
    <Tag
      className={clsx(
        "relative rounded-2xl border border-line bg-surface shadow-card",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

export function CardHeader({
  title,
  eyebrow,
  action,
  className,
}: {
  title: ReactNode;
  eyebrow?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <header className={clsx("flex items-start justify-between gap-4 px-5 pt-5 sm:px-6", className)}>
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-1 text-[11px] font-medium uppercase tracking-[0.14em] text-muted">
            {eyebrow}
          </p>
        )}
        <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "secondary",
  icon: Icon,
  children,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; icon?: LucideIcon }) {
  return (
    <button
      {...props}
      className={clsx(
        "inline-flex h-9 items-center justify-center gap-2 rounded-full px-4 text-sm font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-accent text-accent-ink hover:bg-accent-hover",
        variant === "secondary" &&
          "border border-line-strong bg-surface text-ink hover:border-ink-2 hover:bg-surface-2",
        variant === "ghost" && "text-ink-2 hover:bg-surface-2 hover:text-ink",
        variant === "danger" &&
          "border border-critical/40 text-critical-ink hover:bg-critical/10",
        className,
      )}
    >
      {Icon && <Icon size={16} strokeWidth={1.75} aria-hidden />}
      {children}
    </button>
  );
}

const PACE: Record<PaceStatus, { label: string; icon: LucideIcon; tone: string; dot: string }> = {
  on_track: { label: "On track", icon: CheckCircle2, tone: "text-good-ink", dot: "bg-good" },
  running_hot: {
    label: "Running hot",
    icon: AlertTriangle,
    tone: "text-warning-ink",
    dot: "bg-warning",
  },
  over: { label: "Over budget", icon: CircleAlert, tone: "text-critical-ink", dot: "bg-critical" },
};

/** Status always ships as icon + label, never color alone. */
export function PaceBadge({ status, compact = false }: { status: PaceStatus; compact?: boolean }) {
  const s = PACE[status];
  return (
    <span className={clsx("inline-flex items-center gap-1.5 text-xs font-medium", s.tone)}>
      <s.icon size={14} strokeWidth={2} aria-hidden />
      {!compact && s.label}
      {compact && <span className="sr-only">{s.label}</span>}
    </span>
  );
}

export const paceFill: Record<PaceStatus, string> = {
  on_track: "bg-[var(--series-1)]",
  running_hot: "bg-warning",
  over: "bg-critical",
};

const BIZ: Record<BusinessStatus, { label: string; className: string }> = {
  business: { label: "Business", className: "bg-accent-soft text-accent border-accent/25" },
  review: { label: "Review", className: "bg-brass-soft text-brass border-brass/30" },
  personal: { label: "Personal", className: "bg-surface-2 text-ink-2 border-line" },
};

export function BusinessPill({ status, pct }: { status: BusinessStatus; pct?: number }) {
  const s = BIZ[status];
  return (
    <span
      className={clsx(
        "inline-flex h-6 items-center gap-1 rounded-full border px-2.5 text-xs font-medium whitespace-nowrap",
        s.className,
      )}
    >
      {s.label}
      {status === "business" && pct !== undefined && pct < 100 && (
        <span className="opacity-70">· {pct}%</span>
      )}
    </span>
  );
}

export function Stat({
  label,
  value,
  hint,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("min-w-0", className)}>
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight text-ink">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-ink-2">{hint}</p>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-lg bg-surface-2", className)} />;
}

export function EmptyState({ title, body }: { title: string; body?: string }) {
  return (
    <div className="px-6 py-10 text-center">
      <p className="serif text-xl text-ink">{title}</p>
      {body && <p className="mt-1 text-sm text-ink-2">{body}</p>}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Something went wrong";
  return (
    <p className="m-5 rounded-xl border border-critical/30 bg-critical/5 px-4 py-3 text-sm text-critical-ink">
      Couldn’t load this: {message}. Is the backend running on port 8000?
    </p>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="rise mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="serif text-[34px] leading-tight text-ink sm:text-[40px]">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
