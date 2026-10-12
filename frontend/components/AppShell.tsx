"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/create", label: "Create Project" },
  { href: "/projects", label: "My Projects" },
  { href: "/simulation", label: "3D Simulation", suffix: "/simulation" },
  { href: "/schedule", label: "Schedule", suffix: "/schedule" },
  { href: "/budget", label: "Budget", suffix: "/budget" },
  { href: "/resources", label: "Resources", suffix: "/resources" },
  { href: "/risks", label: "Risk Analysis", suffix: "/risks" },
  { href: "/scenarios", label: "Scenarios", suffix: "/scenarios" },
  { href: "/reports", label: "Reports", suffix: "/reports" },
  { href: "/settings", label: "Settings" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    setActiveId(window.localStorage.getItem("projectverse.activeProjectId"));
    setOpen(false);
  }, [pathname]);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-[#10151c]/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
          <Link href="/" className="font-display text-2xl tracking-tight">
            ProjectVerse <span className="text-amber">AI</span>
          </Link>
          <button className="btn secondary lg:hidden" type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
            {open ? "Close" : "Menu"}
          </button>
          <nav className={`${open ? "flex" : "hidden"} absolute left-0 right-0 top-full flex-col gap-1 border-b border-line bg-[#10151c] p-3 lg:static lg:flex lg:flex-row lg:flex-wrap lg:items-center lg:border-0 lg:bg-transparent lg:p-0`}>
            {LINKS.map((link) => {
              const href = link.suffix ? (activeId ? `/projects/${activeId}${link.suffix}` : "/projects") : link.href;
              const active = pathname === href || (link.href === "/" && pathname === "/");
              return (
                <Link key={link.label} href={href} className={`rounded-full px-3 py-1.5 text-sm ${active ? "bg-white/10 text-amber" : "text-muted hover:text-ink"}`}>
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <div className="border-b border-amber/20 bg-amber/10">
        <p className="mx-auto max-w-7xl px-4 py-2 text-sm text-amber">
          Planning model only. Durations, costs, and 3D geometry are assumptions or calculations, not a quotation or engineering result.
        </p>
      </div>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
