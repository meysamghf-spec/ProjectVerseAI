/** Locale constants shared by server and client components. */

export type Locale = "en" | "fa";

/** Build-time default. English unless NEXT_PUBLIC_DEFAULT_LOCALE=fa. */
export const DEFAULT_LOCALE: Locale = process.env.NEXT_PUBLIC_DEFAULT_LOCALE === "fa" ? "fa" : "en";

export const LOCALE_STORAGE_KEY = "projectverse.locale";
export const IRR_UNIT_STORAGE_KEY = "projectverse.irrUnit";

export function directionOf(locale: Locale): "rtl" | "ltr" {
  return locale === "fa" ? "rtl" : "ltr";
}
