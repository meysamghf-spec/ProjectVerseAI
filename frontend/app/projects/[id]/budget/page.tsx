"use client";

import { OriginBadge } from "@/components/Badges";
import { CategoryChart, SpendChart } from "@/components/Charts";
import { useProjectContext } from "@/components/ProjectProvider";
import { money, titleCase } from "@/lib/format";

export default function BudgetPage() {
  const { project } = useProjectContext();
  if (!project) {
    return null;
  }
  const summary = project.cost_summary;
  const curve = project.latest_simulation?.result?.cumulative_cost || [];
  const categories = Object.entries(summary?.by_category || {})
    .filter(([, amount]) => amount)
    .map(([name, amount]) => ({ name: titleCase(name), amount }));
  return (
    <div className="space-y-4">
      <h1 className="font-display text-4xl">Budget</h1>
      {!summary ? <p className="text-muted">No cost lines have been stored.</p> : null}
      {summary ? (
        <>
          <section className="grid gap-3 sm:grid-cols-3">
            <article className="panel p-4"><p className="text-muted">Estimate</p><p className="font-display text-3xl">{money(summary.total, project.currency)}</p><OriginBadge origin="assumption" /></article>
            <article className="panel p-4"><p className="text-muted">Budget target</p><p className="font-display text-3xl">{money(summary.budget, project.currency)}</p><OriginBadge origin="user" /></article>
            <article className="panel p-4"><p className="text-muted">Variance</p><p className="font-display text-3xl">{money(summary.variance, project.currency)}</p><p className="text-sm text-muted">{summary.overrun ? "Over the stated budget" : "Within the stated budget"}</p></article>
          </section>
          <section className="panel p-4">
            <h2 className="mb-3 font-display text-2xl">Cost by category</h2>
            <CategoryChart data={categories} />
          </section>
          <section className="panel p-4">
            <h2 className="mb-3 font-display text-2xl">Planned cumulative cost</h2>
            <SpendChart data={curve} />
          </section>
          <section className="panel overflow-x-auto p-4">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <thead className="text-muted"><tr><th className="py-2">Line</th><th>Category</th><th>Phase</th><th>Amount</th><th>Source</th><th>In total</th></tr></thead>
              <tbody>
                {summary.lines.map((line) => (
                  <tr key={line.id} className="border-t border-line/70">
                    <td className="py-2">{line.name}</td>
                    <td>{line.category}</td>
                    <td>{line.phase}</td>
                    <td>{money(line.amount, project.currency)}</td>
                    <td>{line.source} {line.source_date || ""}</td>
                    <td>{line.include_in_total ? "Yes" : "Excluded rollup"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </div>
  );
}
