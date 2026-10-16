"use client";

import { useState } from "react";

import { OriginBadge } from "@/components/Badges";
import { GanttChart } from "@/components/Gantt";
import { useProjectContext } from "@/components/ProjectProvider";
import { api } from "@/lib/api";
import { dateLabel, days } from "@/lib/format";

export default function SchedulePage() {
  const { project, reload } = useProjectContext();
  const [message, setMessage] = useState<string | null>(null);
  if (!project) {
    return null;
  }
  const result = project.latest_simulation?.result;
  const tasks = project.tasks.filter((task) => !task.is_summary);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-4xl">Schedule</h1>
          <p className="text-sm text-muted">
            Critical path {days(result?.project_duration)} <OriginBadge origin="calculated" />
          </p>
        </div>
        <button
          className="btn"
          type="button"
          onClick={async () => {
            try {
              await api(`/api/v1/projects/${project.id}/schedule`, { method: "POST", body: JSON.stringify({ set_baseline: false }) });
              await reload();
              setMessage("Schedule recalculated from the stored dependencies.");
            } catch (err) {
              setMessage(err instanceof Error ? err.message : "Schedule failed.");
            }
          }}
        >
          Recalculate
        </button>
      </div>
      {message ? <p className="text-sm text-amber">{message}</p> : null}
      <section className="panel p-4">
        <h2 className="mb-3 font-display text-2xl">Gantt</h2>
        <GanttChart tasks={project.tasks} duration={result?.project_duration ?? null} />
      </section>
      <section className="panel overflow-x-auto p-4">
        <h2 className="mb-3 font-display text-2xl">Tasks</h2>
        <p className="mb-3 text-sm text-muted">Critical path: {(result?.critical_path || []).join(" → ") || "Not calculated."}</p>
        <table className="w-full min-w-[46rem] text-left text-sm">
          <thead className="text-muted">
            <tr>
              <th className="py-2">Code</th>
              <th>Name</th>
              <th>Duration</th>
              <th>Start</th>
              <th>Finish</th>
              <th>Float</th>
              <th>Depends on</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.id} className="border-t border-line/70">
                <td className="py-2">{task.code}</td>
                <td>{task.name}{task.is_critical ? " · Critical" : ""}</td>
                <td>{task.duration}</td>
                <td>{task.start_date ? dateLabel(task.start_date) : task.start_offset}</td>
                <td>{task.finish_date ? dateLabel(task.finish_date) : task.finish_offset}</td>
                <td>{task.total_float}</td>
                <td>{project.dependencies.filter((item) => item.successor_code === task.code).map((item) => item.predecessor_code).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel p-4 text-sm">
        <h2 className="font-display text-2xl">Calculation assumptions</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
          {(result?.assumptions || []).slice(0, 8).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
