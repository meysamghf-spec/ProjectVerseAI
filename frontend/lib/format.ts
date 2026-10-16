import { isoToJalali, toPersianDigits } from "./jalali";
import { DEFAULT_LOCALE, type Locale } from "./locale";

export type IrrUnit = "toman" | "rial";

/** Formatting follows the active interface language. The I18n provider keeps these in sync. */
let activeLocale: Locale = DEFAULT_LOCALE;
let activeIrrUnit: IrrUnit = "toman";

export function setFormatLocale(locale: Locale, irrUnit: IrrUnit = activeIrrUnit): void {
  activeLocale = locale;
  activeIrrUnit = irrUnit;
}

export function formatLocale(): Locale {
  return activeLocale;
}

function numberLocale(locale: Locale): string {
  return locale === "fa" ? "fa-IR" : "en-US";
}

export function number(value: number | null | undefined, digits = 0, locale: Locale = activeLocale): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat(numberLocale(locale), { maximumFractionDigits: digits }).format(value);
}

/**
 * Money. Amounts are stored in the project currency (IRR = rial).
 * Persian UI shows IRR as toman (÷10) by default, or rial; English shows ISO currency formatting.
 */
export function money(
  value: number | null | undefined,
  currency = "USD",
  locale: Locale = activeLocale,
  irrUnit: IrrUnit = activeIrrUnit,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  const code = (currency || "USD").toUpperCase();
  if (code === "IRR" || code === "IRT") {
    const rial = code === "IRT" ? value * 10 : value;
    if (locale === "fa") {
      return irrUnit === "toman" ? `${number(rial / 10, 0, "fa")} تومان` : `${number(rial, 0, "fa")} ریال`;
    }
    return irrUnit === "toman" ? `${number(rial / 10, 0, "en")} toman` : `IRR ${number(rial, 0, "en")}`;
  }
  try {
    return new Intl.NumberFormat(numberLocale(locale), { style: "currency", currency: code, maximumFractionDigits: 0 }).format(value);
  } catch {
    return `${number(value, 0, locale)} ${code}`;
  }
}

export function days(value: number | null | undefined, locale: Locale = activeLocale): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return locale === "fa" ? `${number(value, 1, "fa")} روز` : `${number(value, 1, "en")} days`;
}

export function percent(value: number | null | undefined, locale: Locale = activeLocale): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return locale === "fa" ? "محاسبه نشده" : "Not calculated";
  }
  const rounded = Math.round(value * 1000) / 10;
  return locale === "fa" ? `${number(rounded, 1, "fa")}٪` : `${rounded}%`;
}

/** ISO date (YYYY-MM-DD or a timestamp) -> Gregorian in English, Jalali (Persian digits) in Persian. */
export function dateLabel(iso: string | null | undefined, locale: Locale = activeLocale): string {
  if (!iso) {
    return "—";
  }
  const day = iso.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) {
    return iso;
  }
  if (locale === "fa") {
    return toPersianDigits(isoToJalali(day));
  }
  const [y, m, d] = day.split("-").map(Number);
  return new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }).format(
    new Date(Date.UTC(y, m - 1, d)),
  );
}

export function titleCase(value: string): string {
  return value.replace(/[-_]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
