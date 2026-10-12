"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { Disclaimer, OriginBadge } from "@/components/Badges";
import { useProjectContext } from "@/components/ProjectProvider";
import { WorkspaceFrame } from "@/components/WorkspaceFrame";
import { api } from "@/lib/api";
import { days, money, percent } from "@/lib/format";

const ProjectScene = dynamic(() => import("@/components/ProjectScene"), {
  ssr: false,
  loading: () => <div className="panel grid min-h-[50vh] place-items-center">Loading 3D scene…</div>,
});

export default function ProjectOverviewPage() {
  const { project, reload } = useProjectContext();
  if (!project) {
    return null;
  }
  const result = project.latest_simulation?.result;
  const monte = project.latest_monte_carlo?.result;
  return (
    <WorkspaceFrame
      viewport={<ProjectScene project={project} />}
      side={
        <div className="space-y-4">
          <section className="panel space-y-3 p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-muted">{project.category}</p>
            <h1 className="font-display text-3xl">{project.name}</h1>
            <p className="text-sm text-muted">{project.summary}</p>
            <Disclaimer>{project.disclaimer}</Disclaimer>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-muted">Duration</dt><dd>{days(result?.project_duration)} <OriginBadge origin="calculated" /></dd></div>
              <div><dt className="text-muted">Estimate</dt><dd>{money(result?.total_cost, project.currency)} <OriginBadge origin="assumption" /></dd></div>
              <div><dt className="text-muted">Budget variance</dt><dd>{money(result?.budget_variance, project.currency)}</dd></div>
              <div><dt className="text-muted">P80 duration</dt><dd>{days(monte?.p80_duration)} <OriginBadge origin="simulation" /></dd></div>
              <div><dt className="text-muted">Deadline probability</dt><dd>{percent(monte?.deadline_probability)}</dd></div>
              <div><dt className="text-muted">Budget probability</dt><dd>{percent(monte?.budget_probability)}</dd></div>
            </dl>
            {project.schedule_stale ? <p className="text-sm text-amber">Inputs changed after the last plan. Regenerate to refresh the schedule.</p> : null}
          </section>
          <Inputs projectId={project.id} dimensions={project.dimensions} onSaved={reload} />
          <section className="panel space-y-2 p-4 text-sm">
            <h2 className="font-display text-xl">Warnings</h2>
            {(project.validation.errors.length ? project.validation.errors : project.validation.warnings).slice(0, 6).map((item) => (
              <p key={item}>{item}</p>
            ))}
            {project.validation.errors.length === 0 && project.validation.warnings.length === 0 ? <p className="text-muted">No validation warnings.</p> : null}
          </section>
        </div>
      }
    />
  );
}

function Inputs({
  projectId,
  dimensions,
  onSaved,
}: {
  projectId: string;
  dimensions: Record<string, number | null>;
  onSaved: () => Promise<void>;
}) {
  const [floors, setFloors] = useState(String(dimensions.floors ?? ""));
  const [basements, setBasements] = useState(String(dimensions.basements ?? ""));
  const [gfa, setGfa] = useState(String(dimensions.gfa_sqm ?? ""));
  const [height, setHeight] = useState(String(dimensions.floor_to_floor_height_m ?? 3.2));
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function save(regenerate: boolean) {
    setPending(true);
    setMessage(null);
    try {
      await api(`/api/v1/projects/${projectId}`, {
        method: "PATCH",
        body: JSON.stringify({
          floors: floors ? Number(floors) : undefined,
          basements: basements ? Number(basements) : undefined,
          gfa_sqm: gfa ? Number(gfa) : undefined,
          floor_to_floor_height_m: height ? Number(height) : undefined,
        }),
      });
      if (regenerate) {
        await api(`/api/v1/projects/${projectId}/generate`, {
          method: "POST",
          body: JSON.stringify({ run_monte_carlo: true, iterations: 200, seed: 42, wait: true }),
        });
      }
      await onSaved();
      setMessage(regenerate ? "Plan and simulation were recalculated." : "Scene inputs were saved. The schedule is unchanged until you recalculate.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="panel space-y-3 p-4">
      <h2 className="font-display text-xl">Editable inputs</h2>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <label>Floors<input className="field mt-1" value={floors} onChange={(event) => setFloors(event.target.value)} /></label>
        <label>Basements<input className="field mt-1" value={basements} onChange={(event) => setBasements(event.target.value)} /></label>
        <label>GFA m²<input className="field mt-1" value={gfa} onChange={(event) => setGfa(event.target.value)} /></label>
        <label>Floor height m<input className="field mt-1" value={height} onChange={(event) => setHeight(event.target.value)} /></label>
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="btn secondary" type="button" disabled={pending} onClick={() => save(false)}>Update 3D model</button>
        <button className="btn" type="button" disabled={pending} onClick={() => save(true)}>Recalculate plan</button>
      </div>
      {message ? <p className="text-sm text-muted">{message}</p> : null}
    </section>
  );
}
