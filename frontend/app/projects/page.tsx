"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { dateLabel, money } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { ProjectSummary } from "@/lib/types";

export default function ProjectsPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<ProjectSummary[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (q: string) => {
    const params = new URLSearchParams({ page: "1", page_size: "50" });
    if (q.trim()) params.set("q", q.trim());
    const page = await api<{ items: ProjectSummary[] }>(`/api/v1/projects?${params.toString()}`);
    setItems(page.items);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      load(query).catch((err: Error) => setError(err.message));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query, load]);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-muted">{t("projects.eyebrow")}</p>
          <h1 className="font-display text-4xl">{t("projects.title")}</h1>
        </div>
        <Link className="btn" href="/create">{t("projects.create")}</Link>
      </div>
      <label className="block text-sm">
        {t("projects.search")}
        <input
          className="field mt-1"
          type="search"
          dir="auto"
          placeholder={t("projects.searchPlaceholder")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      {error ? <p className="text-coral">{error}</p> : null}
      {items.length === 0 ? <p className="text-muted">{t("projects.empty")}</p> : null}
      <div className="space-y-3">
        {items.map((project) => (
          <article key={project.id} className="panel flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <h2 className="font-display text-2xl" dir="auto">{project.name}</h2>
              <p className="text-sm text-muted">
                {project.category} · {project.status} · {money(project.budget_amount, project.currency)}
                {project.start_date ? ` · ${dateLabel(project.start_date)}` : ""}
              </p>
            </div>
            <div className="flex gap-2">
              <Link className="btn secondary" href={`/projects/${project.id}`} onClick={() => window.localStorage.setItem("projectverse.activeProjectId", project.id)}>
                {t("projects.open")}
              </Link>
              <button
                className="btn secondary"
                type="button"
                onClick={async () => {
                  if (!window.confirm(`${t("projects.confirmDelete")} ${project.name}`)) {
                    return;
                  }
                  await api(`/api/v1/projects/${project.id}`, { method: "DELETE" });
                  await load(query);
                }}
              >
                {t("projects.delete")}
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
