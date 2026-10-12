"""Persistence models. Project rows are scoped by owner_id."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_owner_created", "owner_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), default="custom")
    original_prompt: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="draft")
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    budget_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    team_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_tolerance: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    work_calendar: Mapped[dict] = mapped_column(JSON, default=dict)
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    scene: Mapped[dict] = mapped_column(JSON, default=dict)
    cost_model: Mapped[dict] = mapped_column(JSON, default=dict)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    schedule_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    specification: Mapped[ProjectSpecification | None] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    tasks: Mapped[list[Task]] = relationship(back_populates="project", cascade="all, delete-orphan")
    dependencies: Mapped[list[TaskDependency]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    resources: Mapped[list[Resource]] = relationship(back_populates="project", cascade="all, delete-orphan")
    cost_items: Mapped[list[CostItem]] = relationship(back_populates="project", cascade="all, delete-orphan")
    milestones: Mapped[list[Milestone]] = relationship(back_populates="project", cascade="all, delete-orphan")
    risks: Mapped[list[Risk]] = relationship(back_populates="project", cascade="all, delete-orphan")
    assumptions: Mapped[list[Assumption]] = relationship(back_populates="project", cascade="all, delete-orphan")
    scenarios: Mapped[list[Scenario]] = relationship(back_populates="project", cascade="all, delete-orphan")
    runs: Mapped[list[SimulationRun]] = relationship(back_populates="project", cascade="all, delete-orphan")
    reports: Mapped[list[Report]] = relationship(back_populates="project", cascade="all, delete-orphan")
    changes: Mapped[list[ProjectChange]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectSpecification(Base):
    __tablename__ = "project_specifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    original_prompt: Mapped[str] = mapped_column(Text, default="")
    project_type: Mapped[str] = mapped_column(String(40), default="custom")
    known: Mapped[list] = mapped_column(JSON, default=list)
    inferred: Mapped[list] = mapped_column(JSON, default=list)
    assumptions: Mapped[list] = mapped_column(JSON, default=list)
    missing: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped[Project] = relationship(back_populates="specification")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_task_project_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    parent_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    wbs_code: Mapped[str] = mapped_column(String(40), default="")
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    is_summary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_milestone: Mapped[bool] = mapped_column(Boolean, default=False)
    scalable: Mapped[bool] = mapped_column(Boolean, default=False)
    phase: Mapped[str] = mapped_column(String(40), default="")
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    duration_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_mode: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_offset: Mapped[float | None] = mapped_column(Float, nullable=True)
    finish_offset: Mapped[float | None] = mapped_column(Float, nullable=True)
    late_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    late_finish: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_float: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_finish: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    finish_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="not_started")
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    project: Mapped[Project] = relationship(back_populates="tasks")
    assignments: Mapped[list[ResourceAssignment]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("predecessor_id", "successor_id", "dependency_type", name="uq_dependency_pair"),
        Index("ix_dependencies_project", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    predecessor_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    successor_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    dependency_type: Mapped[str] = mapped_column(String(8), default="FS")
    lag_days: Mapped[float] = mapped_column(Float, default=0.0)

    project: Mapped[Project] = relationship(back_populates="dependencies")


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_resource_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    resource_type: Mapped[str] = mapped_column(String(40), default="labor")
    unit: Mapped[str] = mapped_column(String(40), default="person")
    available: Mapped[float] = mapped_column(Float, default=1.0)
    rate: Mapped[float] = mapped_column(Float, default=0.0)
    rate_source: Mapped[str] = mapped_column(String(120), default="projectverse-sample-assumptions")
    rate_date: Mapped[str | None] = mapped_column(String(20), nullable=True)

    project: Mapped[Project] = relationship(back_populates="resources")
    assignments: Mapped[list[ResourceAssignment]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )


class ResourceAssignment(Base):
    __tablename__ = "resource_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[float] = mapped_column(Float, default=1.0)

    task: Mapped[Task] = relationship(back_populates="assignments")
    resource: Mapped[Resource] = relationship(back_populates="assignments")


class CostItem(Base):
    __tablename__ = "cost_items"
    __table_args__ = (Index("ix_cost_items_project", "project_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    code: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    phase: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit: Mapped[str] = mapped_column(String(40), default="lump_sum")
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    amount_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_mode: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    include_in_total: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(80), default="assumption")
    source_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    project: Mapped[Project] = relationship(back_populates="cost_items")


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    target_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    forecast_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="planned")

    project: Mapped[Project] = relationship(back_populates="milestones")


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(40), default="general")
    probability: Mapped[float] = mapped_column(Float, default=0.0)
    impact_cost: Mapped[float] = mapped_column(Float, default=0.0)
    impact_schedule_days: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    mitigation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="open")
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)

    project: Mapped[Project] = relationship(back_populates="risks")


class Assumption(Base):
    __tablename__ = "assumptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict | list | str | float | int | bool | None] = mapped_column(JSON, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(40), default="assumption")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    project: Mapped[Project] = relationship(back_populates="assumptions")


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (Index("ix_scenarios_project", "project_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    patch: Mapped[dict] = mapped_column(JSON, default=dict)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped[Project] = relationship(back_populates="scenarios")
    runs: Mapped[list[SimulationRun]] = relationship(back_populates="scenario")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (Index("ix_runs_project_status", "project_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    scenario_id: Mapped[str | None] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True
    )
    run_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="queued")
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    inputs_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="runs")
    scenario: Mapped[Scenario | None] = relationship(back_populates="runs")
    result: Mapped[SimulationResult | None] = relationship(
        back_populates="run", cascade="all, delete-orphan", uselist=False
    )


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), unique=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped[SimulationRun] = relationship(back_populates="result")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("simulation_runs.id", ondelete="SET NULL"), nullable=True)
    format: Mapped[str] = mapped_column(String(16))
    report_type: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str] = mapped_column(String(200))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped[Project] = relationship(back_populates="reports")


class ProjectChange(Base):
    __tablename__ = "project_changes"
    __table_args__ = (Index("ix_changes_project_created", "project_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    change_type: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped[Project] = relationship(back_populates="changes")
