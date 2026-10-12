"""Shared data structures for the simulation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ResourceDemand:
    resource_id: str
    quantity: float


@dataclass
class SchedTask:
    id: str
    name: str
    duration: float
    dependencies: list[str] = field(default_factory=list)
    lags: dict[str, float] = field(default_factory=dict)
    milestone: bool = False
    scalable: bool = False
    phase: str = ""
    wbs_code: str = ""
    description: str = ""
    parent_code: str | None = None
    cost: float = 0.0
    duration_min: float | None = None
    duration_mode: float | None = None
    duration_max: float | None = None
    cost_min: float | None = None
    cost_mode: float | None = None
    cost_max: float | None = None
    resources: list[ResourceDemand] = field(default_factory=list)
    progress: float = 0.0
    status: str = "not_started"


@dataclass
class ScheduledTask:
    id: str
    name: str
    duration: float
    earliest_start: float
    earliest_finish: float
    latest_start: float
    latest_finish: float
    total_float: float
    is_critical: bool
    milestone: bool
    phase: str
    wbs_code: str
    start_date: date | None = None
    finish_date: date | None = None
    exclusive_finish_date: date | None = None
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ScheduleResult:
    ok: bool
    errors: list[str]
    warnings: list[str]
    tasks: list[ScheduledTask]
    project_duration: float
    critical_path: list[str]
    critical_tasks: list[str]
    assumptions: list[str]


@dataclass
class CostLine:
    id: str
    name: str
    category: str
    amount: float
    task_id: str | None = None
    phase: str | None = None
    include_in_total: bool = True
    source: str = "assumption"
    source_date: str | None = None
    notes: str = ""
    amount_min: float | None = None
    amount_mode: float | None = None
    amount_max: float | None = None
    quantity: float = 1.0
    unit: str = "lump_sum"
    unit_cost: float = 0.0


@dataclass
class BudgetResult:
    total: float
    budget: float | None
    variance: float | None
    overrun: bool
    by_category: dict[str, float]
    by_phase: dict[str, float]
    by_task: dict[str, float]
    included_line_ids: list[str]
    excluded_line_ids: list[str]
    assumptions: list[str]


@dataclass
class ResourcePool:
    id: str
    name: str
    available: float
    resource_type: str = "labor"
    unit: str = "crew"
    rate: float = 0.0


@dataclass
class ResourceLoad:
    resource_id: str
    name: str
    available: float
    peak: float
    overloaded: bool
    demand_by_day: dict[int, float]


@dataclass
class ResourceResult:
    resources: list[ResourceLoad]
    conflicts: list[str]
    assumptions: list[str]


@dataclass
class WorkCalendar:
    skip_weekends: bool = False
    hours_per_day: float = 8.0
    days_per_week: int = 7
    holiday_dates: list[date] = field(default_factory=list)

    def assumption_notes(self) -> list[str]:
        if self.skip_weekends:
            notes = [
                "Durations are working days. Saturday, Sunday, and listed holidays are not worked.",
                "Elapsed calendar time can be longer than task duration when non-working days fall inside a task.",
            ]
        else:
            notes = [
                "Durations are calendar days. Weekends are treated as working days.",
                "A successor starts on the predecessor's exclusive finish offset (finish-to-start, lag included).",
            ]
        notes.append(
            f"The calendar records {self.hours_per_day:g} hours per day for reporting. "
            "Duration math uses whole or fractional days, not hours."
        )
        return notes


@dataclass
class ScenarioPatch:
    """Independent scenario edits. Applying a patch must not mutate the baseline."""

    name: str
    description: str
    duration_factors: dict[str, float] = field(default_factory=dict)
    scalable_only: bool = False
    scalable_phases: list[str] = field(default_factory=list)
    cost_category_factors: dict[str, float] = field(default_factory=dict)
    extra_lags: dict[str, float] = field(default_factory=dict)
    # (successor_id, predecessor_id, lag_days). Negative lag overlaps the predecessor.
    lag_overrides: list[tuple[str, str, float]] = field(default_factory=list)
    remove_dependencies: list[tuple[str, str]] = field(default_factory=list)
    add_dependencies: list[tuple[str, str, float]] = field(default_factory=list)
    remove_task_ids: list[str] = field(default_factory=list)
    budget_override: float | None = None
    deadline_day_override: float | None = None
    dimension_overrides: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
