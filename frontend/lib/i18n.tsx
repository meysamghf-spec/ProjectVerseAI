"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { setFormatLocale, type IrrUnit } from "./format";
import { DEFAULT_LOCALE, IRR_UNIT_STORAGE_KEY, LOCALE_STORAGE_KEY, directionOf, type Locale } from "./locale";

export { DEFAULT_LOCALE, directionOf, type Locale };

const en = {
  "nav.dashboard": "Dashboard",
  "nav.create": "Create Project",
  "nav.projects": "My Projects",
  "nav.simulation": "3D Simulation",
  "nav.schedule": "Schedule",
  "nav.budget": "Budget",
  "nav.resources": "Resources",
  "nav.risks": "Risk Analysis",
  "nav.scenarios": "Scenarios",
  "nav.reports": "Reports",
  "nav.settings": "Settings",
  "nav.users": "Users",
  "nav.signin": "Sign in",
  "nav.signout": "Sign out",
  "menu.open": "Menu",
  "menu.close": "Close",
  "lang.switch": "فارسی",
  "lang.label": "Switch the interface to Persian",
  "banner":
    "Planning model only. Durations, costs, and 3D geometry are assumptions or calculations, not a quotation or engineering result.",
  "login.title": "Sign in",
  "login.lead": "Accounts are created by an administrator. Your session is kept in a secure HttpOnly cookie.",
  "login.email": "Email",
  "login.password": "Password",
  "login.submit": "Sign in",
  "login.pending": "Signing in…",
  "login.failed": "Sign-in failed.",
  "projects.eyebrow": "Library",
  "projects.title": "My projects",
  "projects.create": "Create project",
  "projects.search": "Search projects",
  "projects.searchPlaceholder": "Name, location, or description",
  "projects.empty": "No saved projects match.",
  "projects.open": "Open",
  "projects.delete": "Delete",
  "projects.confirmDelete": "Delete this project?",
  "create.start": "Start date",
  "create.deadline": "Deadline",
  "create.budget": "Budget",
  "create.currency": "Currency",
  "create.fx": "Exchange rate (currency per 1 USD, optional)",
  "create.fxHelp": "Sample cost rates are in USD. Without a rate, non-USD totals are flagged as unconverted.",
  "date.jalaliHint": "Jalali date, e.g. 1405/07/24",
  "date.invalid": "Not a valid date.",
  "settings.eyebrow": "Configuration",
  "settings.title": "Settings",
  "settings.language": "Language and formats",
  "settings.languageHelp": "English uses Gregorian dates and ISO currency. Persian uses Jalali dates and Persian digits.",
  "settings.irrUnit": "Show Iranian rial amounts as",
  "settings.toman": "Toman",
  "settings.rial": "Rial",
  "settings.account": "Account",
  "settings.signedInAs": "Signed in as",
  "settings.role": "Role",
  "settings.changePassword": "Change password",
  "settings.currentPassword": "Current password",
  "settings.newPassword": "New password (at least 10 characters)",
  "settings.passwordChanged": "Password changed. Other sessions were signed out.",
  "settings.devIdentity": "Development identity",
  "settings.devHelp":
    "Development mode uses the owner id below. It is not an account system. Production requires user accounts.",
  "settings.devOwner": "Development owner id",
  "settings.save": "Save in this browser",
  "settings.saved": "Saved locally.",
  "users.title": "Users",
  "users.lead": "Create accounts and set roles. There is no public sign-up.",
  "users.email": "Email",
  "users.name": "Display name",
  "users.password": "Initial password (at least 10 characters)",
  "users.role": "Role",
  "users.create": "Create user",
  "users.active": "Active",
  "users.disabled": "Disabled",
  "users.disable": "Disable",
  "users.enable": "Enable",
  "users.makeAdmin": "Make admin",
  "users.makeUser": "Make user",
  "users.lastLogin": "Last sign-in",
  "users.never": "never",
  "role.admin": "Administrator",
  "role.user": "User",
} as const;

export type MessageKey = keyof typeof en;

const fa: Record<MessageKey, string> = {
  "nav.dashboard": "داشبورد",
  "nav.create": "پروژهٔ جدید",
  "nav.projects": "پروژه‌های من",
  "nav.simulation": "شبیه‌سازی سه‌بعدی",
  "nav.schedule": "زمان‌بندی",
  "nav.budget": "بودجه",
  "nav.resources": "منابع",
  "nav.risks": "تحلیل ریسک",
  "nav.scenarios": "سناریوها",
  "nav.reports": "گزارش‌ها",
  "nav.settings": "تنظیمات",
  "nav.users": "کاربران",
  "nav.signin": "ورود",
  "nav.signout": "خروج",
  "menu.open": "منو",
  "menu.close": "بستن",
  "lang.switch": "English",
  "lang.label": "Switch the interface to English",
  "banner":
    "فقط مدل برنامه‌ریزی: مدت‌ها، هزینه‌ها و هندسهٔ سه‌بعدی فرض یا محاسبه هستند، نه پیش‌فاکتور، برآورد قطعی یا نتیجهٔ مهندسی.",
  "login.title": "ورود",
  "login.lead": "حساب‌ها را مدیر سامانه می‌سازد. نشست شما در یک کوکی امن HttpOnly نگه داشته می‌شود.",
  "login.email": "ایمیل",
  "login.password": "گذرواژه",
  "login.submit": "ورود",
  "login.pending": "در حال ورود…",
  "login.failed": "ورود ناموفق بود.",
  "projects.eyebrow": "کتابخانه",
  "projects.title": "پروژه‌های من",
  "projects.create": "پروژهٔ جدید",
  "projects.search": "جست‌وجوی پروژه‌ها",
  "projects.searchPlaceholder": "نام، مکان یا توضیح",
  "projects.empty": "پروژه‌ای پیدا نشد.",
  "projects.open": "باز کردن",
  "projects.delete": "حذف",
  "projects.confirmDelete": "این پروژه حذف شود؟",
  "create.start": "تاریخ شروع",
  "create.deadline": "مهلت پایان",
  "create.budget": "بودجه",
  "create.currency": "واحد پول",
  "create.fx": "نرخ تبدیل (واحد پول به ازای ۱ دلار، اختیاری)",
  "create.fxHelp": "نرخ‌های نمونهٔ هزینه دلاری هستند. بدون نرخ تبدیل، جمع‌های غیر دلاری «تبدیل‌نشده» علامت می‌خورند.",
  "date.jalaliHint": "تاریخ شمسی، مثلاً ۱۴۰۵/۰۷/۲۴",
  "date.invalid": "تاریخ معتبر نیست.",
  "settings.eyebrow": "پیکربندی",
  "settings.title": "تنظیمات",
  "settings.language": "زبان و قالب‌ها",
  "settings.languageHelp": "انگلیسی: تاریخ میلادی و واحد پول بین‌المللی. فارسی: تاریخ شمسی و ارقام فارسی.",
  "settings.irrUnit": "نمایش مبالغ ریالی به",
  "settings.toman": "تومان",
  "settings.rial": "ریال",
  "settings.account": "حساب کاربری",
  "settings.signedInAs": "واردشده با",
  "settings.role": "نقش",
  "settings.changePassword": "تغییر گذرواژه",
  "settings.currentPassword": "گذرواژهٔ فعلی",
  "settings.newPassword": "گذرواژهٔ جدید (حداقل ۱۰ نویسه)",
  "settings.passwordChanged": "گذرواژه تغییر کرد و نشست‌های دیگر بسته شدند.",
  "settings.devIdentity": "هویت حالت توسعه",
  "settings.devHelp": "حالت توسعه از شناسهٔ زیر استفاده می‌کند و سامانهٔ حساب کاربری نیست. نسخهٔ عملیاتی به حساب کاربری نیاز دارد.",
  "settings.devOwner": "شناسهٔ مالک (توسعه)",
  "settings.save": "ذخیره در این مرورگر",
  "settings.saved": "ذخیره شد.",
  "users.title": "کاربران",
  "users.lead": "ساخت حساب و تعیین نقش. ثبت‌نام عمومی وجود ندارد.",
  "users.email": "ایمیل",
  "users.name": "نام نمایشی",
  "users.password": "گذرواژهٔ اولیه (حداقل ۱۰ نویسه)",
  "users.role": "نقش",
  "users.create": "ساخت کاربر",
  "users.active": "فعال",
  "users.disabled": "غیرفعال",
  "users.disable": "غیرفعال کردن",
  "users.enable": "فعال کردن",
  "users.makeAdmin": "مدیر شود",
  "users.makeUser": "کاربر عادی شود",
  "users.lastLogin": "آخرین ورود",
  "users.never": "هرگز",
  "role.admin": "مدیر",
  "role.user": "کاربر",
};

const MESSAGES: Record<Locale, Record<MessageKey, string>> = { en, fa };

export function translate(locale: Locale, key: MessageKey): string {
  return MESSAGES[locale][key] ?? en[key];
}

type I18nValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  irrUnit: IrrUnit;
  setIrrUnit: (unit: IrrUnit) => void;
  t: (key: MessageKey) => string;
};

const I18nContext = createContext<I18nValue>({
  locale: DEFAULT_LOCALE,
  setLocale: () => undefined,
  irrUnit: "toman",
  setIrrUnit: () => undefined,
  t: (key) => translate(DEFAULT_LOCALE, key),
});

function readStored<T extends string>(key: string, allowed: readonly T[]): T | null {
  try {
    const value = window.localStorage.getItem(key);
    return value && (allowed as readonly string[]).includes(value) ? (value as T) : null;
  } catch {
    return null;
  }
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);
  const [irrUnit, setIrrUnitState] = useState<IrrUnit>("toman");

  useEffect(() => {
    const storedLocale = readStored<Locale>(LOCALE_STORAGE_KEY, ["en", "fa"]);
    const storedUnit = readStored<IrrUnit>(IRR_UNIT_STORAGE_KEY, ["toman", "rial"]);
    if (storedLocale) setLocaleState(storedLocale);
    if (storedUnit) setIrrUnitState(storedUnit);
  }, []);

  // Keep module-level formatters, <html lang/dir>, and the cookie in sync with the choice.
  setFormatLocale(locale, irrUnit);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = directionOf(locale);
    document.cookie = `projectverse_locale=${locale}; path=/; max-age=31536000; samesite=lax`;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, next);
    } catch {
      // Storage can be blocked; the choice then lasts for this page view.
    }
  }, []);

  const setIrrUnit = useCallback((next: IrrUnit) => {
    setIrrUnitState(next);
    try {
      window.localStorage.setItem(IRR_UNIT_STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  const value = useMemo<I18nValue>(
    () => ({ locale, setLocale, irrUnit, setIrrUnit, t: (key) => translate(locale, key) }),
    [locale, setLocale, irrUnit, setIrrUnit],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  return useContext(I18nContext);
}
