// Display formatting. Inputs are integer cents.

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const usdWhole = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const usdCompact = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

/** $1,234.56 (always shows cents). */
export function money(cents: number): string {
  return usd.format(cents / 100);
}

/** $1,235 — for headline numbers where cents are noise. */
export function moneyWhole(cents: number): string {
  return usdWhole.format(Math.round(cents / 100));
}

/** $12.9K / $4.2M — for tight spaces like stat tiles and axis ticks. */
export function moneyCompact(cents: number): string {
  return Math.abs(cents) < 100_000 ? moneyWhole(cents) : usdCompact.format(cents / 100);
}

/** Signed amount for transaction lists: "−$12.50" for money out, "+$4,682.40" for money in. */
export function signedMoney(cents: number): string {
  const formatted = usd.format(Math.abs(cents) / 100);
  return cents < 0 ? `−${formatted}` : `+${formatted}`;
}

function parseDay(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** "Oct 9" (adds the year when it differs from `reference`). */
export function shortDate(iso: string, reference: string = new Date().toISOString()): string {
  const d = parseDay(iso);
  const sameYear = d.getFullYear() === parseDay(reference).getFullYear();
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    ...(sameYear ? {} : { year: "numeric" }),
  });
}

/** "October 2026" from "2026-10". */
export function monthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

/** Shift a "YYYY-MM" month by n months. */
export function shiftMonth(month: string, n: number): string {
  const [y, m] = month.split("-").map(Number);
  const idx = y * 12 + (m - 1) + n;
  return `${Math.floor(idx / 12)}-${String((idx % 12) + 1).padStart(2, "0")}`;
}

/** "just now", "3 min ago", "2 h ago". */
export function relativeTime(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

export function greeting(hour: number = new Date().getHours()): string {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}
