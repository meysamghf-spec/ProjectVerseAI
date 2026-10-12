"""Project workflow: extract, persist, schedule, and simulate."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.engine.costs import SAMPLE_RATES
from app.engine.extractor import extract_requirements
from app.engine.llm import (
    DeterministicModel,
    LLMSettings,
    OpenAICompatibleModel,
    merge_model_hints,
)
from app.engine.planner import generate_plan
from app.engine.scenarios import ScenarioPatch, apply_scenario, recompute_percent_costs
from app.engine.scene import construction_scene, generic_scene
from app.engine.types import CostLine, ResourceDemand, SchedTask
from app.models import (
    Assumption,
    CostItem,
    Milestone,
    Project,
    ProjectChange,
    ProjectSpecification,
    Resource,
    ResourceAssignment,
    Risk,
    Scenario,
    SimulationResult,
    SimulationRun,
    Task,
    TaskDependency,
)
from app.services.snapshot import evaluate_monte_carlo, evaluate_snapshot

logger = logging.getLogger("projectverse.planning")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _jsonable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def record_change(db: Session, project: Project, change_type: str, summary: str, before=None, after=None) -> None:
    db.add(
        ProjectChange(
            project_id=project.id,
            change_type=change_type,
            summary=summary,
            before=_jsonable(before) if before is not None else None,
            after=_jsonable(after) if after is not None else None,
        )
    )


def _records(items) -> list[dict]:
    return [
        {
            "key": item.key,
            "value": _jsonable(item.value),
            "origin": item.origin,
            "confidence": item.confidence,
            "note": item.note,
        }
        for item in items
    ]


def interpret_prompt(prompt: str, structured: dict | None, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    structured = dict(structured or {})
    hints = None
    warning = None
    if settings.llm_provider != "deterministic" and settings.llm_api_key:
        model = OpenAICompatibleModel(
            LLMSettings(
                provider=settings.llm_provider,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
            )
        )
        try:
            hints = model.interpret(prompt)
        except Exception as exc:
            logger.warning("Falling back to deterministic extraction after LLM failure: %s", exc.__class__.__name__)
            warning = "The configured language model was unavailable. Deterministic extraction was used."
    else:
        DeterministicModel().interpret(prompt)
    merged = merge_model_hints(structured, hints)
    extraction = extract_requirements(prompt, merged)
    payload = {
        "project_type": extraction.project_type,
        "project_type_origin": extraction.project_type_origin,
        "known": _records(extraction.known),
        "inferred": _records(extraction.inferred),
        "assumptions": _records(extraction.assumptions),
        "missing": extraction.missing,
        "warnings": list(extraction.warnings),
        "confidence": extraction.confidence,
        "values": _jsonable(extraction.values),
        "original_prompt": prompt,
        "llm_used": bool(hints),
    }
    if warning:
        payload["warnings"].append(warning)
    if hints:
        payload["warnings"].append(
            "A language model suggested missing fields. User-supplied values were kept, and schedule math still uses the deterministic engine."
        )
    return payload


def _apply_spec(project: Project, interpreted: dict, db: Session) -> None:
    values = dict(interpreted["values"])
    project.category = str(values.get("project_type") or project.category or "custom")
    project.name = str(values.get("name") or project.name or "Project")[:200]
    project.original_prompt = interpreted["original_prompt"]
    if values.get("currency"):
        project.currency = str(values["currency"])[:8]
    if values.get("budget_amount") is not None:
        project.budget_amount = float(values["budget_amount"])
    if values.get("location"):
        project.location = str(values["location"])[:200]
    if values.get("team_size") is not None:
        project.team_size = int(values["team_size"])
    if values.get("start_date"):
        project.start_date = date.fromisoformat(str(values["start_date"])[:10])
    if values.get("deadline"):
        project.deadline = date.fromisoformat(str(values["deadline"])[:10])
    project.values = values
    project.dimensions = {
        "floors": values.get("floors"),
        "basements": values.get("basements"),
        "gfa_sqm": values.get("gfa_sqm"),
        "floor_to_floor_height_m": values.get("floor_to_floor_height_m"),
        "basement_height_m": values.get("basement_height_m"),
        "aspect_ratio": values.get("aspect_ratio"),
    }
    if not project.work_calendar:
        calendar = values.get("work_calendar") or {}
        project.work_calendar = calendar if isinstance(calendar, dict) else {}
    spec = project.specification
    if spec is None:
        spec = ProjectSpecification(project_id=project.id)
        db.add(spec)
        project.specification = spec
    spec.original_prompt = interpreted["original_prompt"]
    spec.project_type = project.category
    spec.known = interpreted["known"]
    spec.inferred = interpreted["inferred"]
    spec.assumptions = interpreted["assumptions"]
    spec.missing = interpreted["missing"]
    spec.warnings = interpreted["warnings"]
    spec.confidence = interpreted["confidence"]


def create_project(
    db: Session,
    owner_id: str,
    prompt: str,
    structured: dict | None,
    generate: bool,
    run_monte_carlo: bool = False,
    seed: int = 42,
    iterations: int = 200,
) -> Project:
    interpreted = interpret_prompt(prompt, structured)
    project = Project(owner_id=owner_id, name="Project", original_prompt=prompt, status="draft")
    db.add(project)
    db.flush()
    _apply_spec(project, interpreted, db)
    record_change(db, project, "created", "Project created from a natural-language brief.", after={"name": project.name})
    if generate:
        generate_project_plan(
            db,
            project,
            run_monte_carlo=run_monte_carlo,
            seed=seed,
            iterations=iterations,
        )
    project.updated_at = _now()
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: Project, fields: dict) -> Project:
    before = {"name": project.name, "budget_amount": project.budget_amount, "dimensions": project.dimensions}
    dimension_keys = {
        "floors",
        "basements",
        "gfa_sqm",
        "floor_to_floor_height_m",
        "basement_height_m",
        "aspect_ratio",
    }
    values = dict(project.values or {})
    dimensions = dict(project.dimensions or {})
    touched_dimensions = False
    schedule_inputs = {"floors", "basements", "gfa_sqm", "budget_amount", "team_size"}
    for key, value in fields.items():
        if value is None:
            continue
        if key in {"name", "location", "currency", "risk_tolerance"}:
            setattr(project, key, value)
            values[key] = value
        elif key == "budget_amount":
            project.budget_amount = float(value)
            values[key] = float(value)
        elif key == "team_size":
            project.team_size = int(value)
            values[key] = int(value)
        elif key in {"start_date", "deadline"}:
            parsed = date.fromisoformat(str(value)[:10])
            setattr(project, key, parsed)
            values[key] = parsed.isoformat()
        elif key == "category":
            project.category = value
            values["project_type"] = value
        elif key == "prompt":
            project.original_prompt = value
        elif key == "work_calendar":
            project.work_calendar = value
        elif key == "constraints":
            project.constraints = value
        elif key in dimension_keys:
            dimensions[key] = value
            values[key] = value
            touched_dimensions = True
            if key in schedule_inputs:
                project.schedule_stale = True
    project.dimensions = dimensions
    project.values = values
    if touched_dimensions:
        _refresh_scene(project)
    if any(key in fields for key in schedule_inputs):
        project.schedule_stale = True
    project.updated_at = _now()
    record_change(db, project, "updated", "Project inputs were edited.", before=before, after={"name": project.name, "dimensions": dimensions})
    db.commit()
    db.refresh(project)
    return project


def _refresh_scene(project: Project) -> None:
    values = project.values or {}
    if project.category == "construction" and values.get("gfa_sqm") and values.get("floors"):
        project.scene = construction_scene(
            float(values["gfa_sqm"]),
            int(values["floors"]),
            int(values.get("basements") or 0),
            {
                "floor_to_floor_height_m": values.get("floor_to_floor_height_m"),
                "basement_height_m": values.get("basement_height_m"),
                "aspect_ratio": values.get("aspect_ratio"),
            },
        )
    else:
        phases = sorted({task.phase for task in project.tasks if task.phase and not task.is_summary})
        project.scene = generic_scene(project.category, phases)


def _delete_all(db: Session, query) -> None:
    for row in query.all():
        db.delete(row)


def _clear_plan(db: Session, project: Project) -> None:
    task_ids = [row.id for row in db.query(Task.id).filter(Task.project_id == project.id).all()]
    if task_ids:
        _delete_all(db, db.query(ResourceAssignment).filter(ResourceAssignment.task_id.in_(task_ids)))
    _delete_all(db, db.query(TaskDependency).filter(TaskDependency.project_id == project.id))
    _delete_all(db, db.query(CostItem).filter(CostItem.project_id == project.id))
    _delete_all(db, db.query(Milestone).filter(Milestone.project_id == project.id))
    _delete_all(db, db.query(Task).filter(Task.project_id == project.id))
    _delete_all(db, db.query(Resource).filter(Resource.project_id == project.id))
    _delete_all(db, db.query(Risk).filter(Risk.project_id == project.id))
    _delete_all(db, db.query(Assumption).filter(Assumption.project_id == project.id))
    db.flush()


def generate_project_plan(db: Session, project: Project, run_monte_carlo: bool = False, seed: int = 42, iterations: int = 200, wait: bool = True) -> Project:
    interpreted_assumptions = []
    if project.specification:
        interpreted_assumptions = project.specification.assumptions or []
    draft = generate_plan(project.values or {}, interpreted_assumptions)
    _clear_plan(db, project)
    code_to_id: dict[str, str] = {}
    for index, node in enumerate(draft.wbs):
        row = Task(
            project_id=project.id,
            code=node["code"],
            wbs_code=node["code"],
            name=node["name"],
            description="Summary package. Cost is not stored on this row.",
            is_summary=True,
            phase="",
            sort_order=index,
            parent_code=node.get("parent_code"),
        )
        db.add(row)
        db.flush()
        code_to_id[node["code"]] = row.id
    for index, task in enumerate(draft.tasks):
        row = Task(
            project_id=project.id,
            code=task.id,
            wbs_code=task.wbs_code or task.id,
            parent_code=task.parent_code,
            name=task.name,
            description=task.description,
            is_summary=False,
            is_milestone=task.milestone,
            scalable=task.scalable,
            phase=task.phase,
            duration=task.duration,
            duration_min=task.duration_min,
            duration_mode=task.duration_mode,
            duration_max=task.duration_max,
            sort_order=100 + index,
            status="not_started",
        )
        db.add(row)
        db.flush()
        code_to_id[task.id] = row.id
    for task in draft.tasks:
        for pred in task.dependencies:
            db.add(
                TaskDependency(
                    project_id=project.id,
                    predecessor_id=code_to_id[pred],
                    successor_id=code_to_id[task.id],
                    dependency_type="FS",
                    lag_days=float(task.lags.get(pred, 0.0)),
                )
            )
    for pool in draft.resources:
        db.add(
            Resource(
                project_id=project.id,
                code=pool.id,
                name=pool.name,
                resource_type=pool.resource_type,
                unit=pool.unit,
                available=pool.available,
                rate=pool.rate,
                rate_source=SAMPLE_RATES["source"],
                rate_date=SAMPLE_RATES["as_of"],
            )
        )
    db.flush()
    resources = {row.code: row for row in db.query(Resource).filter(Resource.project_id == project.id).all()}
    for task in draft.tasks:
        for demand in task.resources:
            if demand.resource_id not in resources:
                continue
            db.add(
                ResourceAssignment(
                    task_id=code_to_id[task.id],
                    resource_id=resources[demand.resource_id].id,
                    quantity=demand.quantity,
                )
            )
    for line in draft.costs:
        db.add(
            CostItem(
                project_id=project.id,
                task_id=code_to_id.get(line.task_id) if line.task_id else None,
                code=line.id,
                category=line.category,
                name=line.name,
                phase=line.phase,
                quantity=line.quantity,
                unit=line.unit,
                unit_cost=line.unit_cost,
                amount=line.amount,
                amount_min=line.amount_min,
                amount_mode=line.amount_mode,
                amount_max=line.amount_max,
                include_in_total=line.include_in_total,
                source=line.source,
                source_date=line.source_date,
                notes=line.notes,
            )
        )
    for item in draft.risks:
        db.add(
            Risk(
                project_id=project.id,
                code=item["code"],
                title=item["title"],
                description=item["description"],
                category=item["category"],
                probability=item["probability"],
                impact_cost=item["impact_cost"],
                impact_schedule_days=item["impact_schedule_days"],
                score=item["score"],
                mitigation=item["mitigation"],
                status=item["status"],
            )
        )
    for item in draft.milestones:
        db.add(
            Milestone(
                project_id=project.id,
                task_id=code_to_id.get(item["task_code"]),
                code=item["code"],
                name=item["name"],
                status="planned",
            )
        )
    for item in draft.assumptions:
        db.add(
            Assumption(
                project_id=project.id,
                key=str(item.get("key")),
                value=_jsonable(item.get("value")),
                rationale=item.get("rationale") or item.get("note") or "",
                source=item.get("source") or item.get("origin") or "assumption",
                confidence=float(item.get("confidence") or 0),
            )
        )
    project.summary = draft.summary
    project.scene = draft.scene
    project.cost_model = _jsonable(draft.cost_model)
    values = dict(project.values or {})
    values["deliverables"] = draft.deliverables
    project.values = values
    project.plan_generated_at = _now()
    project.schedule_stale = False
    project.status = "ready"
    db.flush()
    execute_simulation(
        db,
        project,
        run_type="deterministic",
        seed=None,
        iterations=None,
        scenario=None,
        set_baseline=True,
    )
    if run_monte_carlo:
        execute_simulation(
            db,
            project,
            run_type="monte_carlo",
            seed=seed,
            iterations=iterations,
            scenario=None,
            set_baseline=False,
        )
    record_change(db, project, "generated", "Project plan, schedule, and cost model were generated.")
    project.updated_at = _now()
    return project


def snapshot_from_project(db: Session, project: Project) -> dict:
    tasks = (
        db.query(Task)
        .filter(Task.project_id == project.id, Task.is_summary.is_(False))
        .order_by(Task.sort_order)
        .all()
    )
    by_id = {task.id: task for task in tasks}
    dependencies = db.query(TaskDependency).filter(TaskDependency.project_id == project.id).all()
    dep_map: dict[str, list[str]] = {}
    lag_map: dict[str, dict[str, float]] = {}
    for dep in dependencies:
        successor = by_id.get(dep.successor_id)
        predecessor = by_id.get(dep.predecessor_id)
        if successor is None or predecessor is None:
            continue
        dep_map.setdefault(successor.code, []).append(predecessor.code)
        if abs(dep.lag_days) > 1e-9:
            lag_map.setdefault(successor.code, {})[predecessor.code] = dep.lag_days
    resources = db.query(Resource).filter(Resource.project_id == project.id).all()
    resource_by_id = {row.id: row for row in resources}
    task_ids = [task.id for task in tasks]
    assignments = []
    if task_ids:
        assignments = db.query(ResourceAssignment).filter(ResourceAssignment.task_id.in_(task_ids)).all()
    assignment_map: dict[str, list[dict]] = {}
    for assignment in assignments:
        task = by_id.get(assignment.task_id)
        resource = resource_by_id.get(assignment.resource_id)
        if task is None or resource is None:
            continue
        assignment_map.setdefault(task.code, []).append(
            {"resource_id": resource.code, "quantity": assignment.quantity}
        )
    task_rows = []
    for task in tasks:
        task_rows.append(
            {
                "id": task.code,
                "name": task.name,
                "description": task.description,
                "duration": task.duration,
                "duration_min": task.duration_min,
                "duration_mode": task.duration_mode,
                "duration_max": task.duration_max,
                "dependencies": dep_map.get(task.code, []),
                "lags": lag_map.get(task.code, {}),
                "milestone": task.is_milestone,
                "scalable": task.scalable,
                "phase": task.phase,
                "wbs_code": task.wbs_code,
                "resources": assignment_map.get(task.code, []),
                "progress": task.progress,
                "status": task.status,
                "baseline_start": task.baseline_start,
                "baseline_finish": task.baseline_finish,
            }
        )
    costs = []
    code_by_task = {task.id: task.code for task in tasks}
    for line in db.query(CostItem).filter(CostItem.project_id == project.id).all():
        costs.append(
            {
                "code": line.code,
                "name": line.name,
                "category": line.category,
                "amount": line.amount,
                "amount_min": line.amount_min,
                "amount_mode": line.amount_mode,
                "amount_max": line.amount_max,
                "phase": line.phase,
                "task_code": code_by_task.get(line.task_id) if line.task_id else None,
                "include_in_total": line.include_in_total,
                "source": line.source,
                "source_date": line.source_date,
                "notes": line.notes,
                "quantity": line.quantity,
                "unit": line.unit,
                "unit_cost": line.unit_cost,
            }
        )
    pools = [
        {
            "code": row.code,
            "name": row.name,
            "available": row.available,
            "resource_type": row.resource_type,
            "unit": row.unit,
            "rate": row.rate,
        }
        for row in resources
    ]
    deadline_day = None
    if project.start_date and project.deadline:
        deadline_day = float((project.deadline - project.start_date).days)
    months = (project.values or {}).get("duration_months")
    if deadline_day is None and months is not None and project.start_date:
        deadline_day = float(months) * float((project.values or {}).get("month_length_days") or 30)
    return {
        "tasks": task_rows,
        "costs": costs,
        "resources": pools,
        "calendar": project.work_calendar or {},
        "budget": project.budget_amount,
        "deadline_day": deadline_day,
        "cost_model": project.cost_model or {},
        "dimensions": project.dimensions or {},
        "start_date": project.start_date.isoformat() if project.start_date else None,
    }


def _write_schedule(db: Session, project: Project, payload: dict, set_baseline: bool) -> None:
    tasks = {
        task.code: task
        for task in db.query(Task).filter(Task.project_id == project.id, Task.is_summary.is_(False)).all()
    }
    by_schedule = {row["id"]: row for row in payload["schedule"]}
    for code, row in tasks.items():
        scheduled = by_schedule.get(code)
        if scheduled is None:
            continue
        row.start_offset = scheduled["earliest_start"]
        row.finish_offset = scheduled["earliest_finish"]
        row.late_start = scheduled["latest_start"]
        row.late_finish = scheduled["latest_finish"]
        row.total_float = scheduled["total_float"]
        row.is_critical = scheduled["is_critical"]
        row.start_date = date.fromisoformat(scheduled["start_date"]) if scheduled["start_date"] else None
        row.finish_date = date.fromisoformat(scheduled["finish_date"]) if scheduled["finish_date"] else None
        row.estimated_cost = float(payload["by_task"].get(code) or 0)
        if set_baseline or row.baseline_start is None:
            row.baseline_duration = row.duration
            row.baseline_start = row.start_offset
            row.baseline_finish = row.finish_offset
    for milestone in db.query(Milestone).filter(Milestone.project_id == project.id).all():
        task = next((item for item in tasks.values() if item.id == milestone.task_id), None)
        if task and task.finish_date:
            milestone.forecast_date = task.finish_date
        elif task and task.start_date:
            milestone.forecast_date = task.start_date
    project.schedule_stale = False
    project.status = "simulated"


def queue_simulation(
    db: Session,
    project: Project,
    *,
    run_type: str,
    seed: int | None,
    iterations: int | None,
    scenario: Scenario | None,
) -> SimulationRun:
    snapshot = scenario.config if scenario is not None else snapshot_from_project(db, project)
    if not snapshot.get("tasks"):
        raise ValueError("The project has no schedulable tasks. Generate a plan first.")
    run = SimulationRun(
        project_id=project.id,
        scenario_id=scenario.id if scenario is not None else None,
        run_type=run_type,
        status="queued",
        seed=seed,
        iterations=iterations,
        engine_version=get_settings().engine_version,
        inputs_snapshot=snapshot,
    )
    db.add(run)
    db.flush()
    return run


def execute_simulation(
    db: Session,
    project: Project,
    *,
    run_type: str,
    seed: int | None,
    iterations: int | None,
    scenario: Scenario | None,
    set_baseline: bool,
    existing: SimulationRun | None = None,
) -> SimulationRun:
    snapshot = existing.inputs_snapshot if existing is not None else (
        scenario.config if scenario is not None else snapshot_from_project(db, project)
    )
    if not snapshot.get("tasks"):
        raise ValueError("The project has no schedulable tasks. Generate a plan first.")
    run = existing or SimulationRun(
        project_id=project.id,
        scenario_id=scenario.id if scenario is not None else None,
        run_type=run_type,
        status="running",
        seed=seed,
        iterations=iterations,
        engine_version=get_settings().engine_version,
        inputs_snapshot=snapshot,
        started_at=_now(),
    )
    if existing is None:
        db.add(run)
    else:
        run.status = "running"
        run.started_at = _now()
    db.flush()
    try:
        if run_type == "monte_carlo":
            if seed is None or iterations is None:
                raise ValueError("Monte Carlo runs require a seed and an iteration count.")
            payload = evaluate_monte_carlo(snapshot, seed, iterations)
        elif run_type == "deterministic":
            payload = evaluate_snapshot(snapshot)
        else:
            raise ValueError(f"Unknown run type '{run_type}'.")
    except ValueError as exc:
        run.status = "failed"
        run.error_message = str(exc)[:500]
        run.completed_at = _now()
        db.flush()
        raise
    result = SimulationResult(run_id=run.id, project_id=project.id, payload=payload)
    db.add(result)
    run.status = "completed"
    run.completed_at = _now()
    run.result = result
    if scenario is None and run_type == "deterministic":
        _write_schedule(db, project, payload, set_baseline=set_baseline)
    db.flush()
    return run


def create_scenario(db: Session, project: Project, patch: ScenarioPatch, raw_patch: dict) -> tuple[Scenario, list[str]]:
    baseline = snapshot_from_project(db, project)
    tasks = [SchedTask(**_sched_kwargs(item)) for item in baseline["tasks"]]
    costs = [_cost_line(item) for item in baseline["costs"]]
    patched_tasks, patched_costs, notes = apply_scenario(tasks, costs, patch)
    model = baseline.get("cost_model") or {}
    patched_costs = recompute_percent_costs(
        patched_costs,
        float(model.get("overhead_pct") or 0),
        float(model.get("contingency_pct") or 0),
    )
    config = dict(baseline)
    config["tasks"] = [_task_dict(task) for task in patched_tasks]
    config["costs"] = [_cost_dict(line) for line in patched_costs]
    if patch.budget_override is not None:
        config["budget"] = patch.budget_override
        notes.append(f"Budget target set to {patch.budget_override:g}.")
    if patch.deadline_day_override is not None:
        config["deadline_day"] = patch.deadline_day_override
        notes.append(f"Deadline offset set to {patch.deadline_day_override:g} days.")
    if patch.dimension_overrides:
        config["dimensions"] = {**(config.get("dimensions") or {}), **patch.dimension_overrides}
        notes.append("Dimension overrides were stored on this scenario only.")
    scenario = Scenario(
        project_id=project.id,
        name=patch.name,
        description=patch.description,
        is_baseline=False,
        patch=raw_patch,
        config=config,
        notes=notes,
    )
    db.add(scenario)
    db.flush()
    record_change(db, project, "scenario", f"Scenario '{patch.name}' stored an independent input snapshot.")
    return scenario, notes


def _sched_kwargs(item: dict) -> dict:
    task = item
    return {
        "id": task["id"],
        "name": task["name"],
        "duration": float(task["duration"]),
        "dependencies": list(task.get("dependencies") or []),
        "lags": {key: float(value) for key, value in (task.get("lags") or {}).items()},
        "milestone": bool(task.get("milestone")),
        "scalable": bool(task.get("scalable")),
        "phase": task.get("phase") or "",
        "wbs_code": task.get("wbs_code") or task["id"],
        "description": task.get("description") or "",
        "duration_min": task.get("duration_min"),
        "duration_mode": task.get("duration_mode"),
        "duration_max": task.get("duration_max"),
        "resources": [
            ResourceDemand(demand["resource_id"], float(demand["quantity"]))
            for demand in task.get("resources") or []
        ],
    }


def _task_dict(task: SchedTask) -> dict:
    return {
        "id": task.id,
        "name": task.name,
        "description": task.description,
        "duration": task.duration,
        "duration_min": task.duration_min,
        "duration_mode": task.duration_mode,
        "duration_max": task.duration_max,
        "dependencies": list(task.dependencies),
        "lags": dict(task.lags),
        "milestone": task.milestone,
        "scalable": task.scalable,
        "phase": task.phase,
        "wbs_code": task.wbs_code,
        "resources": [{"resource_id": item.resource_id, "quantity": item.quantity} for item in task.resources],
        "baseline_start": None,
        "baseline_finish": None,
    }


def _cost_line(item: dict) -> CostLine:
    from app.services.snapshot import cost_from_dict

    return cost_from_dict(item)


def _cost_dict(line: CostLine) -> dict:
    return {
        "code": line.id,
        "name": line.name,
        "category": line.category,
        "amount": line.amount,
        "amount_min": line.amount_min,
        "amount_mode": line.amount_mode,
        "amount_max": line.amount_max,
        "phase": line.phase,
        "task_code": line.task_id,
        "include_in_total": line.include_in_total,
        "source": line.source,
        "source_date": line.source_date,
        "notes": line.notes,
        "quantity": line.quantity,
        "unit": line.unit,
        "unit_cost": line.unit_cost,
    }


def patch_from_payload(payload: dict) -> ScenarioPatch:
    def triples(items, width: int):
        parsed = []
        for item in items or []:
            if len(item) != width:
                raise ValueError("Dependency edits must be fixed-length lists.")
            parsed.append(tuple(item))
        return parsed

    return ScenarioPatch(
        name=payload["name"],
        description=payload.get("description") or "",
        duration_factors={key: float(value) for key, value in (payload.get("duration_factors") or {}).items()},
        scalable_only=bool(payload.get("scalable_only")),
        scalable_phases=list(payload.get("scalable_phases") or []),
        cost_category_factors={
            key: float(value) for key, value in (payload.get("cost_category_factors") or {}).items()
        },
        extra_lags={key: float(value) for key, value in (payload.get("extra_lags") or {}).items()},
        lag_overrides=[(a, b, float(c)) for a, b, c in triples(payload.get("lag_overrides"), 3)],
        remove_dependencies=[(a, b) for a, b in triples(payload.get("remove_dependencies"), 2)],
        add_dependencies=[(a, b, float(c)) for a, b, c in triples(payload.get("add_dependencies"), 3)],
        remove_task_ids=list(payload.get("remove_task_ids") or []),
        budget_override=payload.get("budget_override"),
        deadline_day_override=payload.get("deadline_day_override"),
        dimension_overrides={key: float(value) for key, value in (payload.get("dimension_overrides") or {}).items()},
        notes=list(payload.get("notes") or []),
    )

