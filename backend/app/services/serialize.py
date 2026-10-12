"""Read models into API payloads."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.engine.budget import aggregate_costs
from app.engine.validation import validate_plan
from app.models import (
    Assumption,
    CostItem,
    Milestone,
    Project,
    Resource,
    Risk,
    Scenario,
    SimulationRun,
    Task,
    TaskDependency,
)
from app.services.planning import snapshot_from_project
from app.services.snapshot import calendar_from_dict, cost_from_dict, pool_from_dict, task_from_dict


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def public_result(payload: dict | None, include_samples: bool = False) -> dict | None:
    if not payload:
        return None
    data = dict(payload)
    durations = data.pop("duration_samples", None)
    costs = data.pop("cost_samples", None)
    data["duration_sample_count"] = len(durations or [])
    data["cost_sample_count"] = len(costs or [])
    if durations is not None:
        data["duration_sample_checksum"] = round(sum(durations), 6)
    if costs is not None:
        data["cost_sample_checksum"] = round(sum(costs), 6)
    if include_samples:
        data["duration_samples"] = durations
        data["cost_samples"] = costs
    return data


def run_payload(run: SimulationRun | None, include_samples: bool = False) -> dict | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "project_id": run.project_id,
        "scenario_id": run.scenario_id,
        "run_type": run.run_type,
        "status": run.status,
        "seed": run.seed,
        "iterations": run.iterations,
        "engine_version": run.engine_version,
        "error_message": run.error_message,
        "created_at": _iso(run.created_at),
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
        "result": public_result(run.result.payload if run.result else None, include_samples),
    }


def latest_run(db: Session, project_id: str, run_type: str, scenario_id: str | None = None) -> SimulationRun | None:
    query = db.query(SimulationRun).filter(
        SimulationRun.project_id == project_id,
        SimulationRun.run_type == run_type,
        SimulationRun.status == "completed",
    )
    if scenario_id is None:
        query = query.filter(SimulationRun.scenario_id.is_(None))
    else:
        query = query.filter(SimulationRun.scenario_id == scenario_id)
    return query.order_by(SimulationRun.completed_at.desc()).first()


def project_summary(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "category": project.category,
        "status": project.status,
        "currency": project.currency,
        "budget_amount": project.budget_amount,
        "start_date": _iso(project.start_date),
        "deadline": _iso(project.deadline),
        "location": project.location,
        "schedule_stale": project.schedule_stale,
        "created_at": _iso(project.created_at),
        "updated_at": _iso(project.updated_at),
    }


def project_detail(db: Session, project: Project, include_samples: bool = False) -> dict:
    tasks = (
        db.query(Task).filter(Task.project_id == project.id).order_by(Task.sort_order, Task.code).all()
    )
    dependencies = db.query(TaskDependency).filter(TaskDependency.project_id == project.id).all()
    task_by_id = {task.id: task for task in tasks}
    costs = db.query(CostItem).filter(CostItem.project_id == project.id).all()
    resources = db.query(Resource).filter(Resource.project_id == project.id).all()
    risks = db.query(Risk).filter(Risk.project_id == project.id).order_by(Risk.score.desc()).all()
    assumptions = db.query(Assumption).filter(Assumption.project_id == project.id).all()
    milestones = db.query(Milestone).filter(Milestone.project_id == project.id).all()
    spec = project.specification
    try:
        snapshot = snapshot_from_project(db, project)
        checks = validate_plan(
            [task_from_dict(item) for item in snapshot["tasks"]],
            [cost_from_dict(item) for item in snapshot["costs"]],
            [pool_from_dict(item) for item in snapshot["resources"]],
            start=project.start_date,
            deadline=project.deadline,
            budget=project.budget_amount,
            calendar=calendar_from_dict(project.work_calendar),
            assumptions_present=bool(assumptions),
        ) if snapshot["tasks"] else {"ok": True, "errors": [], "warnings": ["No plan has been generated yet."], "can_continue": True}
    except ValueError as exc:
        checks = {"ok": False, "errors": [str(exc)], "warnings": [], "can_continue": False}
    budget = aggregate_costs([cost_from_dict({
        "code": line.code,
        "name": line.name,
        "category": line.category,
        "amount": line.amount,
        "phase": line.phase,
        "task_code": task_by_id[line.task_id].code if line.task_id in task_by_id else None,
        "include_in_total": line.include_in_total,
    }) for line in costs], project.budget_amount) if costs else None
    detail = {
        **project_summary(project),
        "summary": project.summary,
        "original_prompt": project.original_prompt,
        "team_size": project.team_size,
        "risk_tolerance": project.risk_tolerance,
        "dimensions": project.dimensions or {},
        "work_calendar": project.work_calendar or {},
        "constraints": project.constraints or {},
        "scene": project.scene or {},
        "confidence": spec.confidence if spec else None,
        "deliverables": (project.values or {}).get("deliverables") or [],
        "plan_generated_at": _iso(project.plan_generated_at),
        "specification": None
        if spec is None
        else {
            "project_type": spec.project_type,
            "known": spec.known,
            "inferred": spec.inferred,
            "assumptions": spec.assumptions,
            "missing": spec.missing,
            "warnings": spec.warnings,
            "confidence": spec.confidence,
            "original_prompt": spec.original_prompt,
        },
        "tasks": [
            {
                "id": task.id,
                "code": task.code,
                "parent_code": task.parent_code,
                "name": task.name,
                "description": task.description,
                "is_summary": task.is_summary,
                "is_milestone": task.is_milestone,
                "scalable": task.scalable,
                "phase": task.phase,
                "duration": task.duration,
                "duration_min": task.duration_min,
                "duration_mode": task.duration_mode,
                "duration_max": task.duration_max,
                "start_offset": task.start_offset,
                "finish_offset": task.finish_offset,
                "late_start": task.late_start,
                "late_finish": task.late_finish,
                "total_float": task.total_float,
                "baseline_start": task.baseline_start,
                "baseline_finish": task.baseline_finish,
                "baseline_duration": task.baseline_duration,
                "start_date": _iso(task.start_date),
                "finish_date": _iso(task.finish_date),
                "is_critical": task.is_critical,
                "progress": task.progress,
                "status": task.status,
                "estimated_cost": task.estimated_cost,
                "origin": "calculated" if task.start_offset is not None else "assumption",
            }
            for task in tasks
        ],
        "dependencies": [
            {
                "id": dep.id,
                "predecessor_code": task_by_id[dep.predecessor_id].code if dep.predecessor_id in task_by_id else None,
                "successor_code": task_by_id[dep.successor_id].code if dep.successor_id in task_by_id else None,
                "dependency_type": dep.dependency_type,
                "lag_days": dep.lag_days,
            }
            for dep in dependencies
        ],
        "resources": [
            {
                "id": row.id,
                "code": row.code,
                "name": row.name,
                "resource_type": row.resource_type,
                "unit": row.unit,
                "available": row.available,
                "rate": row.rate,
                "rate_source": row.rate_source,
                "rate_date": row.rate_date,
            }
            for row in resources
        ],
        "cost_summary": None
        if budget is None
        else {
            "total": budget.total,
            "budget": budget.budget,
            "variance": budget.variance,
            "overrun": budget.overrun,
            "by_category": budget.by_category,
            "by_phase": budget.by_phase,
            "assumptions": budget.assumptions,
            "lines": [
                {
                    "id": line.id,
                    "code": line.code,
                    "name": line.name,
                    "category": line.category,
                    "phase": line.phase,
                    "amount": line.amount,
                    "quantity": line.quantity,
                    "unit": line.unit,
                    "unit_cost": line.unit_cost,
                    "include_in_total": line.include_in_total,
                    "source": line.source,
                    "source_date": line.source_date,
                    "notes": line.notes,
                    "task_code": task_by_id[line.task_id].code if line.task_id in task_by_id else None,
                }
                for line in costs
            ],
        },
        "risks": [
            {
                "id": risk.id,
                "code": risk.code,
                "title": risk.title,
                "description": risk.description,
                "category": risk.category,
                "probability": risk.probability,
                "impact_cost": risk.impact_cost,
                "impact_schedule_days": risk.impact_schedule_days,
                "score": risk.score,
                "mitigation": risk.mitigation,
                "status": risk.status,
                "owner": risk.owner,
            }
            for risk in risks
        ],
        "milestones": [
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "target_date": _iso(item.target_date),
                "forecast_date": _iso(item.forecast_date),
                "status": item.status,
                "task_code": task_by_id[item.task_id].code if item.task_id in task_by_id else None,
            }
            for item in milestones
        ],
        "assumptions": [
            {
                "id": item.id,
                "key": item.key,
                "value": item.value,
                "rationale": item.rationale,
                "source": item.source,
                "confidence": item.confidence,
            }
            for item in assumptions
        ],
        "validation": checks,
        "latest_simulation": run_payload(latest_run(db, project.id, "deterministic"), include_samples),
        "latest_monte_carlo": run_payload(latest_run(db, project.id, "monte_carlo"), include_samples),
        "disclaimer": (
            "Figures are planning-model outputs. User-provided facts, assumptions, "
            "calculations, and simulation results are labeled separately and are not a quotation."
        ),
    }
    return detail


def scenario_payload(db: Session, scenario: Scenario) -> dict:
    deterministic = latest_run(db, scenario.project_id, "deterministic", scenario.id)
    monte = latest_run(db, scenario.project_id, "monte_carlo", scenario.id)
    return {
        "id": scenario.id,
        "name": scenario.name,
        "description": scenario.description,
        "is_baseline": scenario.is_baseline,
        "patch": scenario.patch,
        "notes": scenario.notes,
        "created_at": _iso(scenario.created_at),
        "deterministic": run_payload(deterministic),
        "monte_carlo": run_payload(monte),
    }
