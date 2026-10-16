"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface Meta {
  name: string;
  engine_version: string;
  auth_mode: string;
  environment: string;
  llm_provider: string;
  llm_configured: boolean;
  sample_rates: Record<string, unknown>;
  limitations: string[];
}

interface Me {
  auth_mode: string;
  authenticated: boolean;
  user: { email: string; role: string; display_name: string } | null;
}

export default function SettingsPage() {
  const { t, locale, setLocale, irrUnit, setIrrUnit } = useI18n();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [owner, setOwner] = useState("dev-user");
  const [saved, setSaved] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);

  useEffect(() => {
    setOwner(window.localStorage.getItem("projectverse.owner") || "dev-user");
    api<Meta>("/api/v1/meta").then(setMeta).catch((err: Error) => setError(err.message));
    api<Me>("/api/v1/auth/me").then(setMe).catch(() => setMe(null));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.18em] text-muted">{t("settings.eyebrow")}</p>
        <h1 className="font-display text-4xl">{t("settings.title")}</h1>
      </div>
      {error ? <p className="text-coral">{error}</p> : null}
      <section className="panel space-y-3 p-5">
        <h2 className="font-display text-2xl">{t("settings.language")}</h2>
        <p className="text-sm text-muted">{t("settings.languageHelp")}</p>
        <div className="flex flex-wrap gap-2">
          <button className={`btn ${locale === "en" ? "" : "secondary"}`} type="button" onClick={() => setLocale("en")}>English</button>
          <button className={`btn ${locale === "fa" ? "" : "secondary"}`} type="button" onClick={() => setLocale("fa")}>فارسی</button>
        </div>
        <label className="block text-sm">
          {t("settings.irrUnit")}
          <select className="field mt-1" value={irrUnit} onChange={(event) => setIrrUnit(event.target.value as "toman" | "rial")}>
            <option value="toman">{t("settings.toman")}</option>
            <option value="rial">{t("settings.rial")}</option>
          </select>
        </label>
      </section>
      {me?.auth_mode === "accounts" && me.user ? (
        <section className="panel space-y-3 p-5">
          <h2 className="font-display text-2xl">{t("settings.account")}</h2>
          <p className="text-sm">
            {t("settings.signedInAs")} <span dir="ltr">{me.user.email}</span> · {t("settings.role")}: {t(me.user.role === "admin" ? "role.admin" : "role.user")}
          </p>
          <form
            className="grid gap-3 sm:grid-cols-2"
            onSubmit={async (event) => {
              event.preventDefault();
              setPasswordMessage(null);
              try {
                await api("/api/v1/auth/password", {
                  method: "POST",
                  body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
                });
                setCurrentPassword("");
                setNewPassword("");
                setPasswordMessage(t("settings.passwordChanged"));
              } catch (err) {
                setPasswordMessage(err instanceof Error ? err.message : "Error");
              }
            }}
          >
            <label className="text-sm">{t("settings.currentPassword")}<input className="field mt-1" dir="ltr" type="password" autoComplete="current-password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
            <label className="text-sm">{t("settings.newPassword")}<input className="field mt-1" dir="ltr" type="password" autoComplete="new-password" minLength={10} required value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label>
            <div className="sm:col-span-2"><button className="btn" type="submit">{t("settings.changePassword")}</button></div>
            {passwordMessage ? <p className="text-sm text-teal sm:col-span-2">{passwordMessage}</p> : null}
          </form>
        </section>
      ) : null}
      {meta && meta.auth_mode === "development" ? (
        <section className="panel space-y-3 p-5">
          <h2 className="font-display text-2xl">{t("settings.devIdentity")}</h2>
          <p className="text-sm text-muted">{t("settings.devHelp")}</p>
          <label className="block text-sm">
            {t("settings.devOwner")}
            <input className="field mt-1" dir="ltr" value={owner} onChange={(event) => setOwner(event.target.value)} />
          </label>
          <button
            className="btn"
            type="button"
            onClick={() => {
              window.localStorage.setItem("projectverse.owner", owner || "dev-user");
              setSaved(true);
            }}
          >
            {t("settings.save")}
          </button>
          {saved ? <p className="text-sm text-teal">{t("settings.saved")}</p> : null}
        </section>
      ) : null}
      {meta ? (
        <section className="panel space-y-3 p-5">
          <h2 className="font-display text-2xl">{meta.name}</h2>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div><dt className="text-muted">Engine</dt><dd>{meta.engine_version}</dd></div>
            <div><dt className="text-muted">Auth mode</dt><dd>{meta.auth_mode}</dd></div>
            <div><dt className="text-muted">Environment</dt><dd>{meta.environment}</dd></div>
            <div><dt className="text-muted">Language model</dt><dd>{meta.llm_configured ? meta.llm_provider : "deterministic fallback"}</dd></div>
          </dl>
          <h3 className="pt-2 font-medium">Sample rate card</h3>
          <p className="text-sm text-muted">{String(meta.sample_rates.disclaimer || "")}</p>
          <p className="text-sm">Source {String(meta.sample_rates.source)} dated {String(meta.sample_rates.as_of)} (USD).</p>
          <h3 className="pt-2 font-medium">Limitations</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            {meta.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
