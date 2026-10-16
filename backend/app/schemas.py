"""Request and response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    name: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=40)
    start_date: str | None = None
    deadline: str | None = None
    budget_amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)
    usd_exchange_rate: float | None = Field(default=None, gt=0)
    location: str | None = Field(default=None, max_length=200)
    floors: int | None = Field(default=None, ge=0, le=200)
    basements: int | None = Field(default=None, ge=0, le=40)
    gfa_sqm: float | None = Field(default=None, ge=0)
    duration_months: float | None = Field(default=None, ge=0)
    team_size: int | None = Field(default=None, ge=0, le=100000)
    risk_tolerance: str | None = Field(default=None, max_length=40)
    deliverables: list[str] | None = None
    constraints: dict[str, Any] | None = None
    work_calendar: dict[str, Any] | None = None
    labor_rates: dict[str, Any] | None = None
    material_prices: dict[str, Any] | None = None
    equipment: list[str] | None = None
    generate: bool = True
    run_monte_carlo: bool = False
    seed: int = 42
    iterations: int = Field(default=200, ge=2, le=10000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=40)
    prompt: str | None = Field(default=None, max_length=20000)
    start_date: str | None = None
    deadline: str | None = None
    budget_amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)
    usd_exchange_rate: float | None = Field(default=None, gt=0)
    location: str | None = Field(default=None, max_length=200)
    floors: int | None = Field(default=None, ge=0, le=200)
    basements: int | None = Field(default=None, ge=0, le=40)
    gfa_sqm: float | None = Field(default=None, ge=0)
    floor_to_floor_height_m: float | None = Field(default=None, gt=0, le=20)
    basement_height_m: float | None = Field(default=None, gt=0, le=20)
    aspect_ratio: float | None = Field(default=None, gt=0, le=10)
    team_size: int | None = Field(default=None, ge=0)
    risk_tolerance: str | None = None
    work_calendar: dict[str, Any] | None = None
    constraints: dict[str, Any] | None = None


class ExtractRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    name: str | None = None
    category: str | None = None
    start_date: str | None = None
    deadline: str | None = None
    budget_amount: float | None = Field(default=None, ge=0)
    currency: str | None = None
    location: str | None = None
    floors: int | None = Field(default=None, ge=0)
    basements: int | None = Field(default=None, ge=0)
    gfa_sqm: float | None = Field(default=None, ge=0)
    duration_months: float | None = Field(default=None, ge=0)
    team_size: int | None = Field(default=None, ge=0)


class GenerateRequest(BaseModel):
    run_monte_carlo: bool = False
    seed: int = 42
    iterations: int = Field(default=200, ge=2, le=10000)
    wait: bool = True


class TaskCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    duration: float = Field(ge=0)
    phase: str = "custom"
    milestone: bool = False
    scalable: bool = False
    dependencies: list[str] = []
    duration_min: float | None = None
    duration_mode: float | None = None
    duration_max: float | None = None


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    duration: float | None = Field(default=None, ge=0)
    phase: str | None = None
    scalable: bool | None = None
    progress: float | None = Field(default=None, ge=0, le=1)
    status: str | None = Field(default=None, max_length=40)
    duration_min: float | None = None
    duration_mode: float | None = None
    duration_max: float | None = None


class DependencyCreate(BaseModel):
    predecessor_code: str
    successor_code: str
    lag_days: float = 0
    dependency_type: str = "FS"


class CostCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(max_length=200)
    category: str
    amount: float
    phase: str | None = None
    task_code: str | None = None
    include_in_total: bool = True
    source: str = "user"
    source_date: str | None = None
    notes: str = ""
    quantity: float = 1
    unit: str = "lump_sum"


class ScheduleRequest(BaseModel):
    set_baseline: bool = False


class SimulationRequest(BaseModel):
    run_type: str = "deterministic"
    seed: int = 42
    iterations: int = Field(default=200, ge=2, le=10000)
    wait: bool = True
    scenario_id: str | None = None


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    duration_factors: dict[str, float] = {}
    scalable_only: bool = False
    scalable_phases: list[str] = []
    cost_category_factors: dict[str, float] = {}
    extra_lags: dict[str, float] = {}
    lag_overrides: list[list[Any]] = []
    remove_dependencies: list[list[Any]] = []
    add_dependencies: list[list[Any]] = []
    remove_task_ids: list[str] = []
    budget_override: float | None = Field(default=None, ge=0)
    deadline_day_override: float | None = Field(default=None, ge=0)
    dimension_overrides: dict[str, float] = {}
    notes: list[str] = []
    run: bool = True
    monte_carlo: bool = False
    seed: int = 42
    iterations: int = Field(default=80, ge=2, le=10000)
    wait: bool = True


class ReportRequest(BaseModel):
    format: str
    report_type: str = "full"


class Page(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[Any]
    page: int
    page_size: int
    total: int
