import type { Metadata } from "next";
import { Figtree, Fraunces } from "next/font/google";

import { AppShell } from "@/components/AppShell";

import "./globals.css";

const display = Fraunces({ subsets: ["latin"], variable: "--font-display" });
const body = Figtree({ subsets: ["latin"], variable: "--font-body" });

export const metadata: Metadata = {
  title: "ProjectVerse AI",
  description: "Turn a project description into a plan, schedule, budget, and conceptual 3D simulation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${body.variable}`}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
