"use client";

import { useState } from "react";

import { OriginBadge } from "@/components/Badges";
import { DateField } from "@/components/DateField";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { FieldRecord, ProjectDetail } from "@/lib/types";

function toLatin(value: string): string {
  return value.replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d))).replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d))).replace(/٬/g, ",").replace(/٫/g, ".");
}

const EXAMPLE =
  "Plan a 20-story residential building with three basement parking levels, 25,000 square meters of gross floor area, a $15 million budget, and a 30-month construction schedule. Generate a 3D conceptual model, construction phases, project schedule, cost breakdown, resource plan, risk register, and alternative scenarios.";

const EXAMPLE_FA =
  "برنامه‌ریزی ساخت یک ساختمان مسکونی ۱۲ طبقه با ۲ طبقه زیرزمین، ۹۶۰۰ متر مربع زیربنا، بودجه ۱۵۰ میلیارد تومان و مدت ۲۴ ماه در اراک.";

export default function CreatePage() {
  const { t, locale, irrUnit } = useI18n();
  const [prompt, setPrompt] = useState(locale === "fa" ? EXAMPLE_FA : EXAMPLE);
  const [fx, setFx] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [startDate, setStartDate] = useState("");
  const [deadline, setDeadline] = useState("");
  const [budget, setBudget] = useState("");
  const [currency, setCurrency] = useState(locale === "fa" ? "IRR" : "USD");
  // Persian UI with toman display: budgets are typed in toman and stored in rial (x10).
  const budgetInToman = locale === "fa" && irrUnit === "toman" && currency.toUpperCase() === "IRR";
  const [location, setLocation] = useState("");
  const [teamSize, setTeamSize] = useState("");
  const [monteCarlo, setMonteCarlo] = useState(true);
  const [preview, setPreview] = useState<null | {
    known: FieldRecord[];
    inferred: FieldRecord[];
    assumptions: FieldRecord[];
    missing: string[];
    confidence: number;
    warnings: string[];
  }>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const EDITABLE = [
    ["name", "Name"],
    ["floors", "Floors"],
    ["basements", "Basements"],
    ["gfa_sqm", "Gross floor area m²"],
    ["duration_months", "Duration months"],
    ["budget_amount", "Budget"],
    ["team_size", "Team size"],
    ["location", "Location"],
    ["start_date", "Start date"],
  ] as const;

  function extractedValue(key: string): string {
    if (!preview) {
      return "";
    }
    const record = [...preview.known, ...preview.inferred, ...preview.assumptions].find((item) => item.key === key);
    if (!record || record.value == null || typeof record.value === "object") {
      return "";
    }
    return String(record.value);
  }

  function structured() {
    const edited: Record<string, string | number | undefined> = {};
    for (const [key] of EDITABLE) {
      if (!(key in edits)) {
        continue;
      }
      const raw = edits[key].trim();
      if (!raw) {
        continue;
      }
      const numeric = ["floors", "basements", "gfa_sqm", "duration_months", "budget_amount", "team_size"].includes(key);
      const value = numeric ? Number(raw) : raw;
      if (typeof value === "number" && !Number.isFinite(value)) {
        continue;
      }
      edited[key] = value;
    }
    return {
      prompt,
      name: (edited.name as string | undefined) || name || undefined,
      category: category || undefined,
      start_date: (edited.start_date as string | undefined) || startDate || undefined,
      deadline: deadline || undefined,
      budget_amount:
        (edited.budget_amount as number | undefined) ??
        (budget ? Number(toLatin(budget).replace(/,/g, "")) * (budgetInToman ? 10 : 1) : undefined),
      currency: currency.toUpperCase(),
      usd_exchange_rate: fx ? Number(toLatin(fx).replace(/,/g, "")) : undefined,
      location: (edited.location as string | undefined) || location || undefined,
      team_size: (edited.team_size as number | undefined) ?? (teamSize ? Number(teamSize) : undefined),
      floors: edited.floors as number | undefined,
      basements: edited.basements as number | undefined,
      gfa_sqm: edited.gfa_sqm as number | undefined,
      duration_months: edited.duration_months as number | undefined,
    };
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_0.8fr]">
      <form
        className="panel space-y-4 p-5"
        onSubmit={async (event) => {
          event.preventDefault();
          setPending(true);
          setError(null);
          try {
            const project = await api<ProjectDetail>("/api/v1/projects", {
              method: "POST",
              body: JSON.stringify({ ...structured(), generate: true, run_monte_carlo: monteCarlo, iterations: 200, seed: 42 }),
            });
            window.localStorage.setItem("projectverse.activeProjectId", project.id);
            window.location.href = `/projects/${project.id}`;
          } catch (err) {
            setError(err instanceof Error ? err.message : "The project could not be created.");
            setPending(false);
          }
        }}
      >
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-muted">New project</p>
          <h1 className="font-display text-4xl">Describe the work</h1>
        </div>
        <label className="block text-sm">
          Project prompt
          <textarea className="field mt-2 min-h-48" dir="auto" value={prompt} onChange={(event) => setPrompt(event.target.value)} required />
        </label>
        <details className="rounded-xl border border-line p-3">
          <summary className="cursor-pointer">Optional structured inputs</summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-sm">Name<input className="field mt-1" value={name} onChange={(event) => setName(event.target.value)} /></label>
            <label className="text-sm">
              Category
              <select className="field mt-1" value={category} onChange={(event) => setCategory(event.target.value)}>
                <option value="">Infer from the prompt</option>
                {["construction", "software", "manufacturing", "infrastructure", "urban", "logistics", "research", "event", "custom"].map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <DateField label={t("create.start")} value={startDate} onChange={setStartDate} />
            <DateField label={t("create.deadline")} value={deadline} onChange={setDeadline} />
            <label className="text-sm">
              {t("create.budget")}
              {budgetInToman ? " (تومان)" : ""}
              <input className="field mt-1" dir="ltr" inputMode="decimal" value={budget} onChange={(event) => setBudget(event.target.value)} />
            </label>
            <label className="text-sm">
              {t("create.currency")}
              <select className="field mt-1" value={currency} onChange={(event) => setCurrency(event.target.value)}>
                {["USD", "EUR", "GBP", "AED", "TRY", "IRR"].map((code) => (
                  <option key={code} value={code}>{code === "IRR" ? (locale === "fa" ? "ریال/تومان (IRR)" : "Iranian rial (IRR)") : code}</option>
                ))}
              </select>
            </label>
            {currency !== "USD" ? (
              <label className="text-sm sm:col-span-2">
                {t("create.fx")}
                <input className="field mt-1" dir="ltr" inputMode="decimal" value={fx} onChange={(event) => setFx(event.target.value)} />
                <span className="mt-1 block text-xs text-muted">{t("create.fxHelp")}</span>
              </label>
            ) : null}
            <label className="text-sm">Location<input className="field mt-1" value={location} onChange={(event) => setLocation(event.target.value)} /></label>
            <label className="text-sm">Team size<input className="field mt-1" inputMode="numeric" value={teamSize} onChange={(event) => setTeamSize(event.target.value)} /></label>
          </div>
        </details>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={monteCarlo} onChange={(event) => setMonteCarlo(event.target.checked)} />
          Run a seeded 200-iteration uncertainty analysis after the deterministic plan
        </label>
        {error ? <p className="text-sm text-coral">{error}</p> : null}
        <div className="flex flex-wrap gap-2">
          <button className="btn" type="submit" disabled={pending}>{pending ? "Generating plan…" : "Create and simulate"}</button>
          <button
            className="btn secondary"
            type="button"
            onClick={async () => {
              setError(null);
              try {
                const result = await api<{ known: FieldRecord[]; inferred: FieldRecord[]; assumptions: FieldRecord[]; missing: string[]; confidence: number; warnings: string[] }>("/api/v1/extract", {
                  method: "POST",
                  body: JSON.stringify(structured()),
                });
                setPreview(result);
                setEdits({});
              } catch (err) {
                setError(err instanceof Error ? err.message : "Extraction failed.");
              }
            }}
          >
            Preview extraction
          </button>
        </div>
      </form>
      <aside className="panel space-y-4 p-5">
        <h2 className="font-display text-2xl">What will be assumed</h2>
        <p className="text-sm text-muted">
          Missing facts do not block the plan. They are filled with editable assumptions and kept separate from anything you typed. A value stays an assumption until you change it here.
        </p>
        {preview ? (
          <div className="space-y-3 text-sm">
            <p>Coverage score {preview.confidence}. This is not a statistical confidence interval.</p>
            {preview.warnings.map((warning) => (
              <p key={warning} className="text-amber">{warning}</p>
            ))}
            <RecordList title="User-provided" origin="user" records={preview.known} />
            <RecordList title="Inferred" origin="inferred" records={preview.inferred} />
            <RecordList title="Assumptions" origin="assumption" records={preview.assumptions} />
            <div className="space-y-2">
              <h3 className="font-medium">Edit extracted values</h3>
              <p className="text-muted">Edited values are sent as your inputs. Unedited assumptions remain assumptions.</p>
              <div className="grid grid-cols-2 gap-2">
                {EDITABLE.map(([key, label]) => (
                  <label key={key} className="text-xs">
                    {label}
                    <input
                      className="field mt-1"
                      value={key in edits ? edits[key] : extractedValue(key)}
                      onChange={(event) => setEdits((current) => ({ ...current, [key]: event.target.value }))}
                    />
                  </label>
                ))}
              </div>
            </div>
            <div>
              <h3 className="mb-1 font-medium">Missing</h3>
              <p className="text-muted">{preview.missing.join(", ") || "None listed."}</p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted">Preview the extraction before saving, or create the project directly.</p>
        )}
      </aside>
    </div>
  );
}

function RecordList({ title, origin, records }: { title: string; origin: string; records: FieldRecord[] }) {
  return (
    <div>
      <h3 className="mb-1 flex items-center gap-2 font-medium">
        {title} <OriginBadge origin={origin} />
      </h3>
      <ul className="space-y-1 text-muted">
        {records.slice(0, 8).map((record) => (
          <li key={record.key}>
            {record.key}: {typeof record.value === "object" ? JSON.stringify(record.value) : String(record.value)}
          </li>
        ))}
      </ul>
    </div>
  );
}
