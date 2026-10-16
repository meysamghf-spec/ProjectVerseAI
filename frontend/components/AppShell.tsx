"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { api, UNAUTHORIZED_EVENT } from "@/lib/api";
import { I18nProvider, useI18n, type MessageKey } from "@/lib/i18n";

const LINKS: { href: string; label: MessageKey; suffix?: string }[] = [
  { href: "/", label: "nav.dashboard" },
  { href: "/create", label: "nav.create" },
  { href: "/projects", label: "nav.projects" },
  { href: "/simulation", label: "nav.simulation", suffix: "/simulation" },
  { href: "/schedule", label: "nav.schedule", suffix: "/schedule" },
  { href: "/budget", label: "nav.budget", suffix: "/budget" },
  { href: "/resources", label: "nav.resources", suffix: "/resources" },
  { href: "/risks", label: "nav.risks", suffix: "/risks" },
  { href: "/scenarios", label: "nav.scenarios", suffix: "/scenarios" },
  { href: "/reports", label: "nav.reports", suffix: "/reports" },
  { href: "/settings", label: "nav.settings" },
];

export interface SessionUser {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "user";
}

interface SessionInfo {
  auth_mode: string;
  authenticated: boolean;
  user: SessionUser | null;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <I18nProvider>
      <ShellFrame>{children}</ShellFrame>
    </I18nProvider>
  );
}

function ShellFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t, locale, setLocale } = useI18n();
  const [open, setOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [session, setSession] = useState<SessionInfo | null>(null);

  const loadSession = useCallback(async () => {
    try {
      setSession(await api<SessionInfo>("/api/v1/auth/me"));
    } catch {
      setSession(null);
    }
  }, []);

  useEffect(() => {
    setActiveId(window.localStorage.getItem("projectverse.activeProjectId"));
    setOpen(false);
    void loadSession();
  }, [pathname, loadSession]);

  useEffect(() => {
    const onUnauthorized = () => {
      if (window.location.pathname !== "/login") {
        router.push(`/login?next=${encodeURIComponent(window.location.pathname)}`);
      }
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [router]);

  const accounts = session?.auth_mode === "accounts";
  const signedOut = accounts && !session?.authenticated;
  useEffect(() => {
    if (signedOut && pathname !== "/login") {
      router.push(`/login?next=${encodeURIComponent(pathname || "/")}`);
    }
  }, [signedOut, pathname, router]);

  async function signOut() {
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
    } finally {
      setSession(null);
      router.push("/login");
    }
  }

  const links = [...LINKS];
  if (accounts && session?.user?.role === "admin") {
    links.push({ href: "/admin/users", label: "nav.users" });
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-[#10151c]/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
          <Link href="/" className="font-display text-2xl tracking-tight" dir="ltr">
            ProjectVerse <span className="text-amber">AI</span>
          </Link>
          <div className="flex items-center gap-2">
            <button
              className="btn secondary"
              type="button"
              aria-label={t("lang.label")}
              onClick={() => setLocale(locale === "fa" ? "en" : "fa")}
            >
              {t("lang.switch")}
            </button>
            <button className="btn secondary lg:hidden" type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
              {open ? t("menu.close") : t("menu.open")}
            </button>
          </div>
          <nav
            aria-label="Primary"
            className={`${open ? "flex" : "hidden"} absolute left-0 right-0 top-full flex-col gap-1 border-b border-line bg-[#10151c] p-3 lg:static lg:flex lg:flex-row lg:flex-wrap lg:items-center lg:border-0 lg:bg-transparent lg:p-0`}
          >
            {signedOut
              ? null
              : links.map((link) => {
                  const href = link.suffix ? (activeId ? `/projects/${activeId}${link.suffix}` : "/projects") : link.href;
                  const active = pathname === href;
                  return (
                    <Link
                      key={link.label}
                      href={href}
                      className={`rounded-full px-3 py-1.5 text-sm ${active ? "bg-white/10 text-amber" : "text-muted hover:text-ink"}`}
                    >
                      {t(link.label)}
                    </Link>
                  );
                })}
            {accounts && session?.user ? (
              <button className="rounded-full px-3 py-1.5 text-sm text-muted hover:text-ink" type="button" onClick={() => void signOut()}>
                {t("nav.signout")} <span dir="ltr">({session.user.email})</span>
              </button>
            ) : null}
          </nav>
        </div>
      </header>
      <div className="border-b border-amber/20 bg-amber/10">
        <p className="mx-auto max-w-7xl px-4 py-2 text-sm text-amber" role="note">
          {t("banner")}
        </p>
      </div>
      {/* Remount on language change so every page re-renders with the new date and number formats. */}
      <main key={locale} className="mx-auto max-w-7xl px-4 py-6">
        {children}
      </main>
    </div>
  );
}
