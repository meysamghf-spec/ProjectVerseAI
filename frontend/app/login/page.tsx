"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/login")) return "/";
  return value;
}

function LoginForm() {
  const { t } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  return (
    <div className="mx-auto max-w-md space-y-4">
      <div>
        <h1 className="font-display text-4xl">{t("login.title")}</h1>
        <p className="mt-2 text-sm text-muted">{t("login.lead")}</p>
      </div>
      <form
        className="panel space-y-3 p-5"
        onSubmit={async (event) => {
          event.preventDefault();
          setPending(true);
          setError(null);
          try {
            await api("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
            router.push(safeNext(params.get("next")));
          } catch (err) {
            setError(err instanceof Error ? err.message : t("login.failed"));
          } finally {
            setPending(false);
          }
        }}
      >
        <label className="block text-sm">
          {t("login.email")}
          <input className="field mt-1" dir="ltr" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label className="block text-sm">
          {t("login.password")}
          <input className="field mt-1" dir="ltr" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {error ? <p className="text-sm text-coral" role="alert">{error}</p> : null}
        <button className="btn" type="submit" disabled={pending}>
          {pending ? t("login.pending") : t("login.submit")}
        </button>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
