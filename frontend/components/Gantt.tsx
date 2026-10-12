import type { Task } from "@/lib/types";

export function GanttChart({ tasks, duration }: { tasks: Task[]; duration: number | null }) {
  const rows = tasks.filter((task) => !task.is_summary && task.start_offset !== null && task.finish_offset !== null);
  if (!duration || rows.length === 0) {
    return <p className="text-sm text-muted">Schedule offsets have not been calculated yet.</p>;
  }
  return (
    <div className="space-y-2" aria-label="Gantt chart">
      {rows.map((task) => {
        const start = task.start_offset || 0;
        const width = Math.max(((task.duration || 0) / duration) * 100, task.is_milestone ? 1.2 : 0.8);
        return (
          <div key={task.id} className="grid grid-cols-1 items-center gap-1 sm:grid-cols-[11rem_1fr_auto] sm:gap-3">
            <div className="truncate text-sm">
              <span className="text-muted">{task.code}</span> {task.name}
            </div>
            <div className="relative h-5 rounded-full bg-white/5">
              <div
                className={`absolute top-0 h-5 rounded-full ${task.is_critical ? "bg-amber" : "bg-teal"}`}
                style={{ left: `${(start / duration) * 100}%`, width: `${width}%` }}
              />
            </div>
            <div className="text-xs text-muted">
              {task.is_critical ? "Critical" : `Float ${task.total_float ?? 0}`}
            </div>
          </div>
        );
      })}
    </div>
  );
}
