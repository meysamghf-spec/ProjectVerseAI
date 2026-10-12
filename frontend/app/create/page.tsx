"use client";

import { useState } from "react";

import { OriginBadge } from "@/components/Badges";
import { api } from "@/lib/api";
import type { FieldRecord, ProjectDetail } from "@/lib/types";

const EXAMPLE =
  "Plan a 20-story residential building with three basement parking levels, 25,000 square meters of gross floor area, a $15 million budget, and a 30-month construction schedule. Generate a 3D conceptual model, construction phases, project schedule, cost breakdown, resource plan, risk register, and alternative scenarios.";

export default function CreatePage() {
  const [prompt, setPrompt] = useState(EXAMPLE);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [startDate, setStartDate] = useState("");
  const [deadline, setDeadline] = useState("");
  const [budget, setBudget] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [location, setLocation] = useState("");
  const [teamSize, setTeamSize] = useState("");
  const [monteCarlo, setMonteCarlo] = useState(true);
  const [preview, setPreview] = useState<null | {
    known: FieldRecord[];
    assumptions: FieldRecord[];
    missing: string[];
    confidence: number;
    warnings: string[];
  }>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function structured() {
    return {
      prompt,
      name: name || undefined,
      category: category || undefined,
      start_date: startDate || undefined,
      deadline: deadline || undefined,
      budget_amount: budget ? Number(budget) : undefined,
      currency,
      location: location || undefined,
      team_size: teamSize ? Number(teamSize) : undefined,
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
          <textarea className="field mt-2 min-h-48" value={prompt} onChange={(event) => setPrompt(event.target.value)} required />
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
            <label className="text-sm">Start date<input className="field mt-1" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
            <label className="text-sm">Deadline<input className="field mt-1" type="date" value={deadline} onChange={(event) => setDeadline(event.target.value)} /></label>
            <label className="text-sm">Budget<input className="field mt-1" inputMode="decimal" value={budget} onChange={(event) => setBudget(event.target.value)} /></label>
            <label className="text-sm">Currency<input className="field mt-1" value={currency} onChange={(event) => setCurrency(event.target.value)} /></label>
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
                const result = await api<{ known: FieldRecord[]; assumptions: FieldRecord[]; missing: string[]; confidence: number; warnings: string[] }>("/api/v1/extract", {
                  method: "POST",
                  body: JSON.stringify(structured()),
                });
                setPreview(result);
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
          Missing facts do not block the plan. They are filled with editable assumptions and kept separate from anything you typed.
        </p>
        {preview ? (
          <div className="space-y-3 text-sm">
            <p>Coverage score {preview.confidence}. This is not a statistical confidence interval.</p>
            {preview.warnings.map((warning) => (
              <p key={warning} className="text-amber">{warning}</p>
            ))}
            <RecordList title="User-provided" origin="user" records={preview.known} />
            <RecordList title="Assumptions" origin="assumption" records={preview.assumptions} />
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
