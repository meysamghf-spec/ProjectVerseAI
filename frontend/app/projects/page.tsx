"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { money } from "@/lib/format";
import type { ProjectSummary } from "@/lib/types";

export default function ProjectsPage() {
  const [items, setItems] = useState<ProjectSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const page = await api<{ items: ProjectSummary[] }>("/api/v1/projects?page=1&page_size=50");
    setItems(page.items);
  }

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-muted">Library</p>
          <h1 className="font-display text-4xl">My projects</h1>
        </div>
        <Link className="btn" href="/create">Create project</Link>
      </div>
      {error ? <p className="text-coral">{error}</p> : null}
      {items.length === 0 ? <p className="text-muted">No saved projects for this owner.</p> : null}
      <div className="space-y-3">
        {items.map((project) => (
          <article key={project.id} className="panel flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <h2 className="font-display text-2xl">{project.name}</h2>
              <p className="text-sm text-muted">
                {project.category} · {project.status} · {money(project.budget_amount, project.currency)}
              </p>
            </div>
            <div className="flex gap-2">
              <Link className="btn secondary" href={`/projects/${project.id}`} onClick={() => window.localStorage.setItem("projectverse.activeProjectId", project.id)}>
                Open
              </Link>
              <button
                className="btn secondary"
                type="button"
                onClick={async () => {
                  if (!window.confirm(`Delete ${project.name}?`)) {
                    return;
                  }
                  await api(`/api/v1/projects/${project.id}`, { method: "DELETE" });
                  await load();
                }}
              >
                Delete
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
