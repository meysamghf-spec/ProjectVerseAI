"use client";

import { useCallback, useEffect, useState } from "react";

import type { SessionUser } from "@/components/AppShell";
import { api } from "@/lib/api";
import { dateLabel } from "@/lib/format";
import { useI18n } from "@/lib/i18n";

interface AdminUser extends SessionUser {
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
}

export default function UsersPage() {
  const { t } = useI18n();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"user" | "admin">("user");

  const load = useCallback(async () => {
    const payload = await api<{ items: AdminUser[] }>("/api/v1/admin/users");
    setUsers(payload.items);
  }, []);

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
  }, [load]);

  async function update(user: AdminUser, body: Record<string, unknown>) {
    setError(null);
    try {
      await api(`/api/v1/admin/users/${user.id}`, { method: "PATCH", body: JSON.stringify(body) });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed.");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl">{t("users.title")}</h1>
        <p className="mt-2 text-sm text-muted">{t("users.lead")}</p>
      </div>
      {error ? <p className="text-coral" role="alert">{error}</p> : null}
      <form
        className="panel grid gap-3 p-5 sm:grid-cols-2"
        onSubmit={async (event) => {
          event.preventDefault();
          setError(null);
          try {
            await api("/api/v1/admin/users", {
              method: "POST",
              body: JSON.stringify({ email, password, role, display_name: name }),
            });
            setEmail("");
            setName("");
            setPassword("");
            await load();
          } catch (err) {
            setError(err instanceof Error ? err.message : "Create failed.");
          }
        }}
      >
        <label className="text-sm">{t("users.email")}<input className="field mt-1" dir="ltr" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label className="text-sm">{t("users.name")}<input className="field mt-1" value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label className="text-sm">{t("users.password")}<input className="field mt-1" dir="ltr" type="password" minLength={10} required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        <label className="text-sm">
          {t("users.role")}
          <select className="field mt-1" value={role} onChange={(event) => setRole(event.target.value as "user" | "admin")}>
            <option value="user">{t("role.user")}</option>
            <option value="admin">{t("role.admin")}</option>
          </select>
        </label>
        <div className="sm:col-span-2"><button className="btn" type="submit">{t("users.create")}</button></div>
      </form>
      <div className="space-y-3">
        {users.map((user) => (
          <article key={user.id} className="panel flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <h2 className="font-medium" dir="ltr">{user.email}</h2>
              <p className="text-sm text-muted">
                {user.display_name ? `${user.display_name} · ` : ""}
                {t(user.role === "admin" ? "role.admin" : "role.user")} · {user.is_active ? t("users.active") : t("users.disabled")} ·{" "}
                {t("users.lastLogin")}: {user.last_login_at ? dateLabel(user.last_login_at) : t("users.never")}
              </p>
            </div>
            <div className="flex gap-2">
              <button className="btn secondary" type="button" onClick={() => void update(user, { role: user.role === "admin" ? "user" : "admin" })}>
                {user.role === "admin" ? t("users.makeUser") : t("users.makeAdmin")}
              </button>
              <button className="btn secondary" type="button" onClick={() => void update(user, { is_active: !user.is_active })}>
                {user.is_active ? t("users.disable") : t("users.enable")}
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
