import { describe, expect, it } from "vitest";

import { isLeapJalaliYear, isoToJalali, jalaliToIso, toGregorian, toJalali, toLatinDigits } from "./jalali";

describe("jalali calendar", () => {
  it("converts known dates both ways", () => {
    expect(toJalali(2026, 10, 16)).toEqual({ jy: 1405, jm: 7, jd: 24 });
    expect(toJalali(2025, 3, 21)).toEqual({ jy: 1404, jm: 1, jd: 1 }); // Nowruz 1404
    expect(toJalali(2024, 3, 20)).toEqual({ jy: 1403, jm: 1, jd: 1 }); // Nowruz 1403
    expect(toGregorian(1403, 12, 30)).toEqual({ gy: 2025, gm: 3, gd: 20 }); // 1403 is leap
    expect(toGregorian(1357, 11, 22)).toEqual({ gy: 1979, gm: 2, gd: 11 });
  });

  it("knows leap years", () => {
    expect(isLeapJalaliYear(1403)).toBe(true);
    expect(isLeapJalaliYear(1404)).toBe(false);
  });

  it("round-trips every day for several years", () => {
    const start = Date.UTC(2020, 0, 1);
    for (let i = 0; i < 365 * 8; i += 1) {
      const date = new Date(start + i * 86400000);
      const iso = date.toISOString().slice(0, 10);
      expect(jalaliToIso(isoToJalali(iso))).toBe(iso);
    }
  });

  it("parses Persian digits and rejects invalid dates", () => {
    expect(toLatinDigits("۱۴۰۵/۰۷/۲۴")).toBe("1405/07/24");
    expect(jalaliToIso("۱۴۰۵/۰۷/۲۴")).toBe("2026-10-16");
    expect(jalaliToIso("1405-7-24")).toBe("2026-10-16");
    expect(jalaliToIso("1404/12/30")).toBeNull(); // 1404 is not leap
    expect(jalaliToIso("1405/13/01")).toBeNull();
    expect(jalaliToIso("hello")).toBeNull();
    expect(isoToJalali("")).toBe("");
  });
});
