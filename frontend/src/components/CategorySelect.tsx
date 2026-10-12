import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { api } from "../lib/api";
import type { Category } from "../lib/types";

const GROUP_LABELS: Record<Category["group"], string> = {
  essential: "Household essentials",
  discretionary: "Household lifestyle",
  business: "S-Corp expenses",
  income: "Income",
  transfer: "Transfers",
  taxes: "Taxes",
  other: "Other",
};
const GROUP_ORDER: Category["group"][] = [
  "essential",
  "discretionary",
  "business",
  "income",
  "transfer",
  "taxes",
  "other",
];

export function useCategories() {
  return useQuery({ queryKey: ["categories"], queryFn: api.categories, staleTime: Infinity });
}

export function CategorySelect({
  value,
  onChange,
  className,
  disabled,
  includeAll = false,
}: {
  value: string;
  onChange: (id: string) => void;
  className?: string;
  disabled?: boolean;
  includeAll?: boolean;
}) {
  const { data = [] } = useCategories();
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Category"
      className={clsx(
        "h-8 max-w-full rounded-lg border border-line bg-surface px-2 text-sm text-ink",
        "hover:border-line-strong focus:border-brass",
        className,
      )}
    >
      {includeAll && <option value="">All categories</option>}
      {GROUP_ORDER.map((group) => {
        const items = data.filter((c) => c.group === group);
        if (!items.length) return null;
        return (
          <optgroup key={group} label={GROUP_LABELS[group]}>
            {items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.irs_line && group === "business" ? ` · 1120-S line ${c.irs_line}` : ""}
              </option>
            ))}
          </optgroup>
        );
      })}
    </select>
  );
}
