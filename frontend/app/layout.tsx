import type { Metadata } from "next";

import { AppShell } from "@/components/AppShell";
import { DEFAULT_LOCALE, directionOf } from "@/lib/locale";

import "./globals.css";

export const metadata: Metadata = {
  title: "ProjectVerse AI",
  description: "Turn a project description into a plan, schedule, budget, and conceptual 3D simulation.",
};

// No Google Fonts: the build must work on servers that cannot reach fonts.googleapis.com.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang={DEFAULT_LOCALE} dir={directionOf(DEFAULT_LOCALE)}>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
