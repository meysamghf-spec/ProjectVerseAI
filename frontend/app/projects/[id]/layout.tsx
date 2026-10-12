"use client";

import { ProjectNav } from "@/components/ProjectNav";
import { ProjectProvider, useProjectContext } from "@/components/ProjectProvider";

function ProjectGate({ children }: { children: React.ReactNode }) {
  const { loading, error, project } = useProjectContext();
  if (loading && !project) {
    return <p className="text-muted">Loading project…</p>;
  }
  if (error && !project) {
    return (
      <div className="panel p-6">
        <h1 className="font-display text-3xl">Project unavailable</h1>
        <p className="mt-2 text-muted">{error}</p>
      </div>
    );
  }
  return <>{children}</>;
}

export default function ProjectLayout({ children, params }: { children: React.ReactNode; params: { id: string } }) {
  return (
    <ProjectProvider id={params.id}>
      <ProjectNav id={params.id} />
      <ProjectGate>{children}</ProjectGate>
    </ProjectProvider>
  );
}
