"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

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

export default function SettingsPage() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [owner, setOwner] = useState("dev-user");
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setOwner(window.localStorage.getItem("projectverse.owner") || "dev-user");
    setApiKey(window.localStorage.getItem("projectverse.apiKey") || "");
    api<Meta>("/api/v1/meta")
      .then(setMeta)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.18em] text-muted">Configuration</p>
        <h1 className="font-display text-4xl">Settings</h1>
      </div>
      {error ? <p className="text-coral">{error}</p> : null}
      <section className="panel space-y-3 p-5">
        <h2 className="font-display text-2xl">Local identity</h2>
        <p className="text-sm text-muted">
          Development mode uses the owner id below. It is not an account system, and the header can be changed by anyone who can reach a development server. Production mode ignores that header and requires an API key.
        </p>
        <label className="block text-sm">
          Development owner id
          <input className="field mt-1" value={owner} onChange={(event) => setOwner(event.target.value)} />
        </label>
        <label className="block text-sm">
          API key for production mode
          <input className="field mt-1" type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} />
        </label>
        <button
          className="btn"
          type="button"
          onClick={() => {
            window.localStorage.setItem("projectverse.owner", owner || "dev-user");
            if (apiKey) {
              window.localStorage.setItem("projectverse.apiKey", apiKey);
            } else {
              window.localStorage.removeItem("projectverse.apiKey");
            }
            setSaved(true);
          }}
        >
          Save in this browser
        </button>
        {saved ? <p className="text-sm text-teal">Saved locally. Reload a project page to use the new identity.</p> : null}
      </section>
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
          <p className="text-sm">Source {String(meta.sample_rates.source)} dated {String(meta.sample_rates.as_of)}.</p>
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
