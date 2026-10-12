"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Disclaimer } from "@/components/Badges";
import { api } from "@/lib/api";
import { days, money, percent } from "@/lib/format";
import type { DashboardCard, SimulationRun } from "@/lib/types";

export default function DashboardPage() {
  const [projects, setProjects] = useState<DashboardCard[]>([]);
  const [runs, setRuns] = useState<SimulationRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<{ projects: DashboardCard[]; recent_runs: SimulationRun[] }>("/api/v1/dashboard")
      .then((payload) => {
        setProjects(payload.projects);
        setRuns(payload.recent_runs);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-muted">Workspace</p>
          <h1 className="font-display text-4xl">Dashboard</h1>
        </div>
        <div className="flex gap-2">
          <Link className="btn secondary" href="/create">
            Create project
          </Link>
          <DemoButton />
        </div>
      </div>
      {loading ? <p className="text-muted">Loading projects…</p> : null}
      {error ? <Disclaimer>{error}</Disclaimer> : null}
      {!loading && projects.length === 0 ? (
        <section className="panel p-6">
          <h2 className="font-display text-2xl">No projects yet</h2>
          <p className="mt-2 max-w-2xl text-muted">
            Describe a project in one prompt, or open the residential tower demonstration. The demonstration uses sample assumptions and does not need an API key.
          </p>
        </section>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        {projects.map((project) => (
          <Link key={project.id} href={`/projects/${project.id}`} className="panel block p-5 hover:border-amber/50">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-muted">{project.category}</p>
                <h2 className="font-display text-2xl">{project.name}</h2>
              </div>
              <span className="badge calculated">{project.status}</span>
            </div>
            <p className="mt-3 line-clamp-3 text-sm text-muted">{project.summary}</p>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-muted">Schedule</dt>
                <dd>{days(project.duration_days)}</dd>
              </div>
              <div>
                <dt className="text-muted">Estimate</dt>
                <dd>{money(project.total_cost, project.currency)}</dd>
              </div>
              <div>
                <dt className="text-muted">Budget variance</dt>
                <dd>{money(project.budget_variance, project.currency)}</dd>
              </div>
              <div>
                <dt className="text-muted">Deadline probability</dt>
                <dd>{percent(project.latest_monte_carlo?.result?.deadline_probability)}</dd>
              </div>
            </dl>
            {project.milestones.length ? (
              <p className="mt-3 text-sm">Next milestone: {project.milestones[0].name}</p>
            ) : null}
            {project.risks[0] ? <p className="text-sm text-coral">Risk: {project.risks[0].title}</p> : null}
          </Link>
        ))}
      </div>
      <section className="panel p-5">
        <h2 className="font-display text-2xl">Recent simulation runs</h2>
        {runs.length === 0 ? <p className="mt-2 text-sm text-muted">No simulation runs yet.</p> : null}
        <ul className="mt-3 space-y-2 text-sm">
          {runs.map((run) => (
            <li key={run.id} className="flex flex-wrap justify-between gap-2 border-b border-line/70 py-2">
              <span>
                {run.run_type} · {run.status}
              </span>
              <span className="text-muted">
                {run.result ? days(run.result.project_duration) : run.error_message || "Pending"} · {run.engine_version}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function DemoButton() {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  return (
    <div>
      <button
        className="btn"
        type="button"
        disabled={pending}
        onClick={async () => {
          setPending(true);
          setMessage(null);
          try {
            const project = await api<{ id: string }>("/api/v1/demo/residential-tower", { method: "POST" });
            window.localStorage.setItem("projectverse.activeProjectId", project.id);
            window.location.href = `/projects/${project.id}`;
          } catch (err) {
            setMessage(err instanceof Error ? err.message : "The demonstration could not be created.");
            setPending(false);
          }
        }}
      >
        {pending ? "Building demonstration…" : "Load tower demonstration"}
      </button>
      {message ? <p className="mt-2 text-sm text-coral">{message}</p> : null}
    </div>
  );
}
