import { describe, expect, it } from "vitest";

import { dateLabel, days, money, percent } from "./format";

describe("locale-aware formatting", () => {
  it("formats English with Gregorian dates and ISO currency", () => {
    expect(money(15000000, "USD", "en")).toBe("$15,000,000");
    expect(money(1000, "EUR", "en")).toBe("€1,000");
    expect(dateLabel("2026-10-16", "en")).toBe("Oct 16, 2026");
    expect(days(12.5, "en")).toBe("12.5 days");
    expect(percent(0.256, "en")).toBe("25.6%");
  });

  it("formats Persian with Jalali dates, Persian digits, and toman/rial", () => {
    expect(dateLabel("2026-10-16", "fa")).toBe("۱۴۰۵/۰۷/۲۴");
    expect(money(1_500_000_000_000, "IRR", "fa", "toman")).toBe("۱۵۰٬۰۰۰٬۰۰۰٬۰۰۰ تومان");
    expect(money(1_500_000_000_000, "IRR", "fa", "rial")).toBe("۱٬۵۰۰٬۰۰۰٬۰۰۰٬۰۰۰ ریال");
    expect(money(1_500_000_000_000, "IRR", "en", "rial")).toBe("IRR 1,500,000,000,000");
    expect(days(3, "fa")).toBe("۳ روز");
    expect(money(null, "USD", "fa")).toBe("—");
  });
});
