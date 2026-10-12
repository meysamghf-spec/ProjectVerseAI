"use client";

import dynamic from "next/dynamic";

import { useProjectContext } from "@/components/ProjectProvider";

const ProjectScene = dynamic(() => import("@/components/ProjectScene"), {
  ssr: false,
  loading: () => <div className="panel grid min-h-[70vh] place-items-center">Loading 3D scene…</div>,
});

export default function SimulationPage() {
  const { project } = useProjectContext();
  if (!project) {
    return null;
  }
  return (
    <div className="space-y-3">
      <h1 className="font-display text-4xl">3D simulation</h1>
      <div className="min-h-[70vh]">
        <ProjectScene project={project} />
      </div>
    </div>
  );
}
