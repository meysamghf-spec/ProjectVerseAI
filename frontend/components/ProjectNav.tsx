"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "", label: "Overview" },
  { href: "/simulation", label: "3D Simulation" },
  { href: "/schedule", label: "Schedule" },
  { href: "/budget", label: "Budget" },
  { href: "/resources", label: "Resources" },
  { href: "/risks", label: "Risk Analysis" },
  { href: "/scenarios", label: "Scenarios" },
  { href: "/reports", label: "Reports" },
];

export function ProjectNav({ id }: { id: string }) {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex gap-2 overflow-x-auto pb-1" aria-label="Project sections">
      {ITEMS.map((item) => {
        const href = `/projects/${id}${item.href}`;
        const active = pathname === href;
        return (
          <Link key={item.href} href={href} className={`whitespace-nowrap rounded-full px-3 py-1.5 text-sm ${active ? "bg-amber text-[#1b1408]" : "bg-white/5 text-muted"}`}>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
