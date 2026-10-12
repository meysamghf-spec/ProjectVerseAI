"use client";

import { useCallback, useEffect, useState } from "react";

import { useProjectContext } from "@/components/ProjectProvider";
import { api } from "@/lib/api";
import { days, money, percent } from "@/lib/format";

interface Comparison {
  baseline: {
    duration: number;
    total_cost: number;
    critical_path: string[];
    deadline_probability: number | null;
    budget_probability: number | null;
    resource_conflicts: string[];
  };
  scenarios: Array<{
    scenario_id: string;
    name: string;
    description: string;
    input_changes: string[];
    duration: number | null;
    duration_delta: number | null;
    total_cost: number | null;
    cost_delta: number | null;
    critical_path: string[] | null;
    resource_conflicts: string[] | null;
    deadline_probability: number | null;
    budget_probability: number | null;
    simulated: boolean;
  }>;
  disclaimer: string;
}

export default function ScenariosPage() {
  const { project, reload } = useProjectContext();
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("Custom alternative");
  const [materialFactor, setMaterialFactor] = useState("1");
  const [phase, setPhase] = useState("superstructure");
  const [durationFactor, setDurationFactor] = useState("1");
  const [scalableOnly, setScalableOnly] = useState(true);
  const [pending, setPending] = useState(false);

  const load = useCallback(async () => {
    if (!project) {
      return;
    }
    try {
      const payload = await api<Comparison>(`/api/v1/projects/${project.id}/scenarios/compare`, { method: "POST" });
      setComparison(payload);
      setError(null);
    } catch (err) {
      setComparison(null);
      setError(err instanceof Error ? err.message : "Comparison is unavailable.");
    }
  }, [project]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!project) {
    return null;
  }

  async function createScenario(body: Record<string, unknown>) {
    setPending(true);
    setError(null);
    try {
      await api(`/api/v1/projects/${project!.id}/scenarios`, {
        method: "POST",
        body: JSON.stringify({ run: true, wait: true, monte_carlo: true, iterations: 80, seed: 42, ...body }),
      });
      await reload();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The scenario could not be created.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="font-display text-4xl">Scenarios</h1>
      <p className="max-w-3xl text-sm text-muted">
        Each scenario stores its own input snapshot. Adding workers changes duration only when you set a factor, and only on the tasks you mark. The baseline tasks stay as they are.
      </p>
      {error ? <p className="text-sm text-coral">{error}</p> : null}
      <section className="panel grid gap-3 p-4 md:grid-cols-3">
        <button className="btn secondary" type="button" disabled={pending} onClick={() => createScenario({
          name: "Increased structure workforce",
          description: "12% productivity on scalable structure and interior tasks. A 20% crew increase is not applied as a 20% duration cut.",
          duration_factors: { superstructure: Number((1 / 1.12).toFixed(4)), interiors: Number((1 / 1.12).toFixed(4)) },
          scalable_only: true,
          scalable_phases: ["superstructure", "interiors"],
          notes: ["Crew scale input 1.20.", "Productivity factor 1.12 on scalable tasks only."],
        })}>Workforce +20% crews</button>
        <button className="btn secondary" type="button" disabled={pending} onClick={() => createScenario({
          name: "Higher material prices",
          description: "Material allowances increased 15 percent. Overhead and contingency are reapplied.",
          cost_category_factors: { materials: 1.15 },
        })}>Materials +15%</button>
        <button className="btn secondary" type="button" disabled={pending} onClick={() => createScenario({
          name: "Accelerated facade overlap",
          description: "Facade starts 120 days before superstructure finishes. The shared crane may overload.",
          lag_overrides: [["CON-ENV", "CON-SUPER", -120]],
        })}>Overlap facade</button>
      </section>
      <form
        className="panel grid gap-3 p-4 md:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          const factors: Record<string, number> = {};
          if (Number(durationFactor) !== 1 && phase) {
            factors[phase] = Number(durationFactor);
          }
          const costs: Record<string, number> = {};
          if (Number(materialFactor) !== 1) {
            costs.materials = Number(materialFactor);
          }
          void createScenario({
            name,
            description: "User-configured alternative.",
            duration_factors: factors,
            scalable_only: scalableOnly,
            scalable_phases: scalableOnly ? [phase] : [],
            cost_category_factors: costs,
          });
        }}
      >
        <label className="text-sm">Name<input className="field mt-1" value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label className="text-sm">Phase factor applies to<input className="field mt-1" value={phase} onChange={(event) => setPhase(event.target.value)} /></label>
        <label className="text-sm">Duration multiplier<input className="field mt-1" value={durationFactor} onChange={(event) => setDurationFactor(event.target.value)} /></label>
        <label className="text-sm">Material cost multiplier<input className="field mt-1" value={materialFactor} onChange={(event) => setMaterialFactor(event.target.value)} /></label>
        <label className="flex items-center gap-2 text-sm md:col-span-2">
          <input type="checkbox" checked={scalableOnly} onChange={(event) => setScalableOnly(event.target.checked)} />
          Apply the duration multiplier only to tasks marked scalable
        </label>
        <button className="btn md:col-span-2" type="submit" disabled={pending}>{pending ? "Running scenario…" : "Create scenario"}</button>
      </form>
      {comparison ? (
        <section className="space-y-3">
          <p className="text-sm text-muted">{comparison.disclaimer}</p>
          <article className="panel p-4 text-sm">
            <h2 className="font-display text-2xl">Baseline</h2>
            <p>{days(comparison.baseline.duration)} · {money(comparison.baseline.total_cost, project.currency)}</p>
            <p>Deadline probability {percent(comparison.baseline.deadline_probability)} · Budget probability {percent(comparison.baseline.budget_probability)}</p>
            <p className="text-muted">Critical path: {comparison.baseline.critical_path.join(" → ")}</p>
          </article>
          {comparison.scenarios.map((scenario) => (
            <article key={scenario.scenario_id} className="panel p-4 text-sm">
              <h2 className="font-display text-2xl">{scenario.name}</h2>
              <p className="text-muted">{scenario.description}</p>
              {scenario.simulated ? (
                <>
                  <p className="mt-2">{days(scenario.duration)} ({scenario.duration_delta && scenario.duration_delta > 0 ? "+" : ""}{scenario.duration_delta} days) · {money(scenario.total_cost, project.currency)} ({money(scenario.cost_delta, project.currency)})</p>
                  <p>Deadline probability {percent(scenario.deadline_probability)} · Budget probability {percent(scenario.budget_probability)}</p>
                  <p>Critical path: {(scenario.critical_path || []).join(" → ") || "Not calculated."}</p>
                  {(scenario.resource_conflicts || []).map((item) => (
                    <p key={item} className="text-coral">{item}</p>
                  ))}
                </>
              ) : (
                <p className="mt-2">This scenario has not been simulated.</p>
              )}
              <ul className="mt-2 list-disc pl-5 text-muted">
                {scenario.input_changes.map((change) => (
                  <li key={change}>{change}</li>
                ))}
              </ul>
            </article>
          ))}
        </section>
      ) : null}
    </div>
  );
}
