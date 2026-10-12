import { describe, expect, it } from "vitest";
import {
  greeting,
  money,
  moneyCompact,
  moneyWhole,
  monthLabel,
  relativeTime,
  shiftMonth,
  shortDate,
  signedMoney,
} from "./format";

describe("money formatting", () => {
  it("formats cents with and without fractions", () => {
    expect(money(123456)).toBe("$1,234.56");
    expect(money(-1250)).toBe("-$12.50");
    expect(moneyWhole(123456)).toBe("$1,235");
  });

  it("compacts large values only", () => {
    expect(moneyCompact(98_700)).toBe("$987");
    expect(moneyCompact(1_290_000)).toBe("$12.9K");
    expect(moneyCompact(420_000_000)).toBe("$4.2M");
  });

  it("signs transaction amounts with a true minus", () => {
    expect(signedMoney(-1250)).toBe("−$12.50");
    expect(signedMoney(468240)).toBe("+$4,682.40");
  });
});

describe("dates", () => {
  it("formats short dates relative to a reference year", () => {
    expect(shortDate("2026-10-09", "2026-10-11")).toBe("Oct 9");
    expect(shortDate("2025-12-31", "2026-10-11")).toBe("Dec 31, 2025");
  });

  it("labels and shifts months", () => {
    expect(monthLabel("2026-10")).toBe("October 2026");
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
  });

  it("describes elapsed time", () => {
    const now = new Date("2026-10-11T12:00:00Z").getTime();
    expect(relativeTime("2026-10-11T11:59:50Z", now)).toBe("just now");
    expect(relativeTime("2026-10-11T11:57:00Z", now)).toBe("3 min ago");
    expect(relativeTime("2026-10-11T09:00:00Z", now)).toBe("3 h ago");
  });

  it("greets by time of day", () => {
    expect(greeting(8)).toBe("Good morning");
    expect(greeting(14)).toBe("Good afternoon");
    expect(greeting(21)).toBe("Good evening");
  });
});
