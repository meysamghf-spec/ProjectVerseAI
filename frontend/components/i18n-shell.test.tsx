import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: () => undefined }),
}));

import { AppShell } from "./AppShell";
import { money } from "@/lib/format";

function Price() {
  return <p data-testid="price">{money(1_500_000_000_000, "IRR")}</p>;
}

describe("language toggle", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
  });

  it("defaults to English LTR and persists a switch to Persian RTL", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ auth_mode: "development", authenticated: true, user: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    render(<AppShell><Price /></AppShell>);
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeTruthy();
    expect(document.documentElement.dir).toBe("ltr");
    expect(screen.getByTestId("price").textContent).toBe("150,000,000,000 toman");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Switch the interface to Persian" }));
    });
    expect(screen.getByRole("link", { name: "داشبورد" })).toBeTruthy();
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("fa");
    expect(window.localStorage.getItem("projectverse.locale")).toBe("fa");
    expect(screen.getByTestId("price").textContent).toBe("۱۵۰٬۰۰۰٬۰۰۰٬۰۰۰ تومان");
    expect(screen.getByRole("note").textContent).toContain("فقط مدل برنامه‌ریزی");
  });

  it("restores the saved language on the next visit", async () => {
    window.localStorage.setItem("projectverse.locale", "fa");
    await act(async () => {
      render(<AppShell><Price /></AppShell>);
    });
    expect(document.documentElement.dir).toBe("rtl");
    expect(screen.getByRole("link", { name: "پروژه‌های من" })).toBeTruthy();
  });
});
