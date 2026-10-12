"use client";

import { useState } from "react";

import { useProjectContext } from "@/components/ProjectProvider";
import { downloadReport } from "@/lib/api";

const FORMATS = ["json", "csv", "pdf", "xlsx"] as const;
const TYPES = [
  ["full", "Full report"],
  ["summary", "Project summary"],
  ["schedule", "Task schedule"],
  ["budget", "Budget breakdown"],
  ["resources", "Resource summary"],
  ["risks", "Risk register"],
  ["scenarios", "Scenario comparison"],
] as const;

export default function ReportsPage() {
  const { project } = useProjectContext();
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  if (!project) {
    return null;
  }
  return (
    <div className="space-y-4">
      <h1 className="font-display text-4xl">Reports</h1>
      <p className="max-w-3xl text-sm text-muted">
        Downloads are generated from the saved plan and the latest simulation. They include the engine version, timestamp, and the model disclaimer.
      </p>
      {message ? <p className="text-sm text-amber">{message}</p> : null}
      <div className="grid gap-3 md:grid-cols-2">
        {TYPES.map(([type, label]) => (
          <section key={type} className="panel p-4">
            <h2 className="font-display text-2xl">{label}</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {FORMATS.map((format) => (
                <button
                  key={format}
                  className="btn secondary"
                  type="button"
                  disabled={pending !== null}
                  onClick={async () => {
                    setPending(`${type}-${format}`);
                    setMessage(null);
                    try {
                      await downloadReport(project.id, format, type);
                      setMessage(`${label} ${format.toUpperCase()} downloaded.`);
                    } catch (err) {
                      setMessage(err instanceof Error ? err.message : "Download failed.");
                    } finally {
                      setPending(null);
                    }
                  }}
                >
                  {pending === `${type}-${format}` ? "Preparing…" : format.toUpperCase()}
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
