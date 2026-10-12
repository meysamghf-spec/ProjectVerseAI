"use client";

import { useProjectContext } from "@/components/ProjectProvider";
import { money } from "@/lib/format";

export default function RisksPage() {
  const { project } = useProjectContext();
  if (!project) {
    return null;
  }
  const contributors = project.latest_monte_carlo?.result?.schedule_contributors || [];
  return (
    <div className="space-y-4">
      <h1 className="font-display text-4xl">Risk analysis</h1>
      <section className="panel overflow-x-auto p-4">
        <table className="w-full min-w-[48rem] text-left text-sm">
          <thead className="text-muted"><tr><th className="py-2">Risk</th><th>Category</th><th>Probability</th><th>Cost impact</th><th>Days</th><th>Score</th><th>Mitigation</th></tr></thead>
          <tbody>
            {project.risks.map((risk) => (
              <tr key={risk.id} className="border-t border-line/70 align-top">
                <td className="py-2"><strong>{risk.title}</strong><p className="text-muted">{risk.description}</p></td>
                <td>{risk.category}</td>
                <td>{risk.probability}</td>
                <td>{money(risk.impact_cost, project.currency)}</td>
                <td>{risk.impact_schedule_days}</td>
                <td>{risk.score}</td>
                <td>{risk.mitigation}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {project.risks.length === 0 ? <p className="text-sm text-muted">No risks have been recorded.</p> : null}
      </section>
      <section className="panel p-4">
        <h2 className="font-display text-2xl">Schedule sensitivity</h2>
        <p className="mt-1 text-sm text-muted">Correlation between each sampled duration and the sampled project duration. This is not a measured risk ranking.</p>
        <ul className="mt-3 space-y-1 text-sm">
          {contributors.slice(0, 6).map((item) => (
            <li key={item.id}>{item.name}: {item.correlation.toFixed(2)}</li>
          ))}
        </ul>
        {contributors.length === 0 ? <p className="mt-2 text-sm text-muted">Run an uncertainty simulation to populate contributors.</p> : null}
      </section>
    </div>
  );
}
