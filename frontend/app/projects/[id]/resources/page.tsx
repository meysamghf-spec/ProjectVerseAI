"use client";

import { useProjectContext } from "@/components/ProjectProvider";

export default function ResourcesPage() {
  const { project } = useProjectContext();
  if (!project) {
    return null;
  }
  const peaks = project.latest_simulation?.result?.resource_peaks || [];
  const conflicts = project.latest_simulation?.result?.resource_conflicts || [];
  return (
    <div className="space-y-4">
      <h1 className="font-display text-4xl">Resources</h1>
      <section className="panel p-4">
        <h2 className="font-display text-2xl">Overload warnings</h2>
        {conflicts.length === 0 ? <p className="mt-2 text-sm text-muted">The latest deterministic run did not find a resource overload.</p> : null}
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
          {conflicts.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
      <section className="panel overflow-x-auto p-4">
        <table className="w-full text-left text-sm">
          <thead className="text-muted"><tr><th className="py-2">Resource</th><th>Available</th><th>Peak</th><th>Status</th><th>Rate source</th></tr></thead>
          <tbody>
            {project.resources.map((resource) => {
              const peak = peaks.find((item) => item.id === resource.code);
              return (
                <tr key={resource.id} className="border-t border-line/70">
                  <td className="py-2">{resource.name}</td>
                  <td>{resource.available} {resource.unit}</td>
                  <td>{peak ? peak.peak : "Not calculated"}</td>
                  <td>{peak?.overloaded ? "Overloaded" : peak ? "Within availability" : "—"}</td>
                  <td>{resource.rate_source} {resource.rate_date || ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {project.resources.length === 0 ? <p className="text-sm text-muted">No resources have been generated.</p> : null}
      </section>
    </div>
  );
}
