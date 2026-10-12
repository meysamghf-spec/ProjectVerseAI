export type Origin = "user" | "inferred" | "assumption" | "calculated" | "simulation";

export interface FieldRecord {
  key: string;
  value: unknown;
  origin: string;
  confidence: number;
  note: string;
}

export interface Task {
  id: string;
  code: string;
  parent_code: string | null;
  name: string;
  description: string;
  is_summary: boolean;
  is_milestone: boolean;
  scalable: boolean;
  phase: string;
  duration: number;
  duration_min: number | null;
  duration_mode: number | null;
  duration_max: number | null;
  start_offset: number | null;
  finish_offset: number | null;
  late_start: number | null;
  late_finish: number | null;
  total_float: number | null;
  baseline_start: number | null;
  baseline_finish: number | null;
  baseline_duration: number | null;
  start_date: string | null;
  finish_date: string | null;
  is_critical: boolean;
  progress: number;
  status: string;
  estimated_cost: number;
  origin: string;
}

export interface CostLine {
  id: string;
  code: string;
  name: string;
  category: string;
  phase: string | null;
  amount: number;
  quantity: number;
  unit: string;
  unit_cost: number;
  include_in_total: boolean;
  source: string;
  source_date: string | null;
  notes: string;
  task_code: string | null;
}

export interface CostSummary {
  total: number;
  budget: number | null;
  variance: number | null;
  overrun: boolean;
  by_category: Record<string, number>;
  by_phase: Record<string, number>;
  assumptions: string[];
  lines: CostLine[];
}

export interface SimulationResult {
  kind: string;
  project_duration: number;
  critical_path: string[];
  critical_tasks: string[];
  completion_date: string | null;
  total_cost: number;
  budget: number | null;
  budget_variance: number | null;
  budget_overrun: boolean;
  by_category: Record<string, number>;
  by_phase: Record<string, number>;
  gantt: Array<Record<string, unknown>>;
  cumulative_cost: Array<{ day: number; cost: number }>;
  resource_conflicts: string[];
  resource_peaks: Array<{
    id: string;
    name: string;
    peak: number;
    available: number;
    overloaded: boolean;
    demand_by_day: Record<string, number>;
  }>;
  warnings: string[];
  assumptions: string[];
  deadline_variance_days: number | null;
  p50_duration: number | null;
  p80_duration: number | null;
  p90_duration: number | null;
  p50_cost: number | null;
  p80_cost: number | null;
  p90_cost: number | null;
  deadline_probability: number | null;
  budget_probability: number | null;
  schedule_contributors: Array<{ id: string; name: string; correlation: number }>;
  cost_contributors: Array<{ id: string; name: string; correlation: number }>;
  disclaimer: string;
  seed?: number;
  iterations?: number;
  duration_sample_count?: number;
  cost_sample_count?: number;
}

export interface SimulationRun {
  id: string;
  run_type: string;
  status: string;
  seed: number | null;
  iterations: number | null;
  engine_version: string;
  error_message: string | null;
  completed_at: string | null;
  result: SimulationResult | null;
}

export interface SceneParams {
  metaphor?: string;
  label?: string;
  disclaimer?: string;
  floors?: number;
  basements?: number;
  gfa_sqm?: number;
  footprint_sqm?: number;
  floor_height_m?: number;
  basement_height_m?: number;
  width_m?: number;
  length_m?: number;
  core_width_m?: number;
  core_length_m?: number;
  column_spacing_m?: number;
  phases?: string[];
  rules?: string[];
}

export interface ProjectDetail {
  id: string;
  name: string;
  category: string;
  status: string;
  currency: string;
  budget_amount: number | null;
  start_date: string | null;
  deadline: string | null;
  location: string | null;
  summary: string;
  original_prompt: string;
  team_size: number | null;
  schedule_stale: boolean;
  dimensions: Record<string, number | null>;
  work_calendar: Record<string, unknown>;
  scene: SceneParams;
  confidence: number | null;
  deliverables: string[];
  specification: {
    project_type: string;
    known: FieldRecord[];
    inferred: FieldRecord[];
    assumptions: FieldRecord[];
    missing: string[];
    warnings: string[];
    confidence: number;
    original_prompt: string;
  } | null;
  tasks: Task[];
  dependencies: Array<{
    id: string;
    predecessor_code: string | null;
    successor_code: string | null;
    dependency_type: string;
    lag_days: number;
  }>;
  resources: Array<{
    id: string;
    code: string;
    name: string;
    resource_type: string;
    unit: string;
    available: number;
    rate: number;
    rate_source: string;
    rate_date: string | null;
  }>;
  cost_summary: CostSummary | null;
  risks: Array<{
    id: string;
    code: string;
    title: string;
    description: string;
    category: string;
    probability: number;
    impact_cost: number;
    impact_schedule_days: number;
    score: number;
    mitigation: string;
    status: string;
  }>;
  milestones: Array<{
    id: string;
    code: string;
    name: string;
    target_date: string | null;
    forecast_date: string | null;
    status: string;
    task_code: string | null;
  }>;
  assumptions: Array<{
    id: string;
    key: string;
    value: unknown;
    rationale: string;
    source: string;
    confidence: number;
  }>;
  validation: { ok: boolean; errors: string[]; warnings: string[]; can_continue: boolean };
  latest_simulation: SimulationRun | null;
  latest_monte_carlo: SimulationRun | null;
  disclaimer: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  category: string;
  status: string;
  currency: string;
  budget_amount: number | null;
  start_date: string | null;
  deadline: string | null;
  location: string | null;
  schedule_stale: boolean;
  created_at: string;
  updated_at: string;
}

export interface DashboardCard extends ProjectSummary {
  summary: string;
  duration_days: number | null;
  total_cost: number | null;
  budget_variance: number | null;
  critical_path: string[];
  milestones: Array<{ name: string; forecast_date: string | null; status: string }>;
  risks: Array<{ title: string; score: number; status: string }>;
  latest_simulation: SimulationRun | null;
  latest_monte_carlo: SimulationRun | null;
}
