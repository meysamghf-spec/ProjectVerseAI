"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ProjectDetail } from "@/lib/types";

interface ProjectContextValue {
  project: ProjectDetail | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ id, children }: { id: string; children: React.ReactNode }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(async () => {
    setError(null);
    try {
      const detail = await api<ProjectDetail>(`/api/v1/projects/${id}`);
      setProject(detail);
      window.localStorage.setItem("projectverse.activeProjectId", id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The project could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return <ProjectContext.Provider value={{ project, loading, error, reload }}>{children}</ProjectContext.Provider>;
}

export function useProjectContext(): ProjectContextValue {
  const value = useContext(ProjectContext);
  if (!value) {
    throw new Error("useProjectContext must be used inside a project workspace.");
  }
  return value;
}
