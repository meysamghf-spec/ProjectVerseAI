"""Versioned HTTP API."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import check_database, get_db
from app.engine import ENGINE_VERSION
from app.engine.budget import COST_CATEGORIES
from app.engine.costs import SAMPLE_RATES
from app.models import (
    CostItem,
    Project,
    ProjectChange,
    Scenario,
    SimulationRun,
    Task,
    TaskDependency,
)
from app.schemas import (
    CostCreate,
    DependencyCreate,
    ExtractRequest,
    GenerateRequest,
    ProjectCreate,
    ProjectUpdate,
    ReportRequest,
    ScenarioCreate,
    ScheduleRequest,
    SimulationRequest,
    TaskCreate,
    TaskUpdate,
)
from app.services.demo import seed_residential_demo
from app.services.jobs import submit_run
from app.services.planning import (
    create_project,
    create_scenario,
    execute_simulation,
    generate_project_plan,
    interpret_prompt,
    patch_from_payload,
    queue_simulation,
    record_change,
    snapshot_from_project,
    update_project,
)
from app.services.reports import collect_document, render_report, store_report
from app.services.serialize import latest_run, project_detail, project_summary, run_payload, scenario_payload
from app.services.snapshot import evaluate_snapshot

router = APIRouter(prefix="/api/v1")


def api_error(status: int, code: str, message: str, details=None) -> NoReturn:
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    from fastapi import HTTPException

    raise HTTPException(status_code=status, detail=body)


def get_owner(request: Request, settings: Settings = Depends(get_settings)) -> str:
    if settings.auth_mode == "development":
        owner = (request.headers.get("x-owner-id") or settings.dev_owner_id).strip()
        if not owner:
            api_error(401, "unauthorized", "Development mode requires an owner id.")
        return owner[:120]
    token = request.headers.get("x-api-key") or ""
    authorization = request.headers.get("authorization") or ""
    if authorization.lower().startswith("bearer "):
        token = token or authorization[7:].strip()
    if not settings.api_key or token != settings.api_key:
        api_error(401, "unauthorized", "A valid API key is required.")
    return settings.api_owner_id


def owned_project(db: Session, owner: str, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != owner:
        api_error(404, "not_found", "Project not found.")
    return project


def _structured_from_create(payload: ProjectCreate | ExtractRequest) -> dict:
    data = payload.model_dump(exclude_none=True)
    data.pop("prompt", None)
    data.pop("generate", None)
    return data


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "projectverse-ai", "engine_version": ENGINE_VERSION}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> JSONResponse:
    if not check_database():
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": False})
    db.execute(text("SELECT 1"))
    return JSONResponse(status_code=200, content={"status": "ready", "database": True})


@router.get("/meta")
def meta(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "name": "ProjectVerse AI",
        "engine_version": ENGINE_VERSION,
        "auth_mode": settings.auth_mode,
        "environment": settings.app_env,
        "llm_provider": settings.llm_provider if settings.llm_api_key else "deterministic",
        "llm_configured": bool(settings.llm_api_key and settings.llm_base_url),
        "sample_rates": SAMPLE_RATES,
        "limitations": [
            "Development authentication is a shared local owner, not an account system.",
            "Production mode requires PROJECTVERSE_API_KEY via the API_KEY environment variable.",
            "Sample rates are bundled assumptions dated 2026-01-01, not live market prices.",
            "The 3D view is conceptual massing or a diagram, not a design model.",
            "Monte Carlo percentiles describe this model's seeded samples only.",
            "Language-model output is optional and is never allowed to run generated code.",
        ],
    }


@router.get("/dashboard")
def dashboard(
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    projects = (
        db.query(Project).filter(Project.owner_id == owner).order_by(Project.updated_at.desc()).limit(12).all()
    )
    cards = []
    for project in projects:
        deterministic = latest_run(db, project.id, "deterministic")
        monte = latest_run(db, project.id, "monte_carlo")
        result = deterministic.result.payload if deterministic and deterministic.result else {}
        top_risks = sorted(project.risks, key=lambda risk: risk.score, reverse=True)[:3]
        upcoming = [
            {
                "name": item.name,
                "forecast_date": item.forecast_date.isoformat() if item.forecast_date else None,
                "status": item.status,
            }
            for item in project.milestones
        ]
        cards.append(
            {
                **project_summary(project),
                "summary": project.summary,
                "duration_days": result.get("project_duration"),
                "total_cost": result.get("total_cost"),
                "budget_variance": result.get("budget_variance"),
                "critical_path": result.get("critical_path") or [],
                "milestones": upcoming,
                "risks": [{"title": risk.title, "score": risk.score, "status": risk.status} for risk in top_risks],
                "latest_simulation": run_payload(deterministic),
                "latest_monte_carlo": run_payload(monte),
            }
        )
    runs = (
        db.query(SimulationRun)
        .join(Project, Project.id == SimulationRun.project_id)
        .filter(Project.owner_id == owner)
        .order_by(SimulationRun.created_at.desc())
        .limit(8)
        .all()
    )
    return {"projects": cards, "recent_runs": [run_payload(run) for run in runs]}


@router.post("/extract")
def extract(payload: ExtractRequest, settings: Settings = Depends(get_settings)) -> dict:
    return interpret_prompt(payload.prompt, _structured_from_create(payload), settings)


@router.post("/projects", status_code=201)
def create(payload: ProjectCreate, owner: str = Depends(get_owner), db: Session = Depends(get_db)) -> dict:
    project = create_project(
        db,
        owner,
        payload.prompt,
        _structured_from_create(payload),
        payload.generate,
        run_monte_carlo=payload.run_monte_carlo,
        seed=payload.seed,
        iterations=payload.iterations,
    )
    return project_detail(db, project)


@router.get("/projects")
def list_projects(
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    query = db.query(Project).filter(Project.owner_id == owner)
    total = query.count()
    rows = query.order_by(Project.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [project_summary(row) for row in rows], "page": page, "page_size": page_size, "total": total}


@router.get("/projects/{project_id}")
def get_project(
    project_id: str,
    include_samples: bool = False,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    project = owned_project(db, owner, project_id)
    return project_detail(db, project, include_samples=include_samples)


@router.patch("/projects/{project_id}")
def patch_project(
    project_id: str,
    payload: ProjectUpdate,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    project = owned_project(db, owner, project_id)
    update_project(db, project, payload.model_dump(exclude_unset=True))
    return project_detail(db, project)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, owner: str = Depends(get_owner), db: Session = Depends(get_db)) -> Response:
    project = owned_project(db, owner, project_id)
    db.delete(project)
    db.commit()
    return Response(status_code=204)


@router.post("/projects/{project_id}/extract")
def extract_into_project(
    project_id: str,
    payload: ExtractRequest,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    project = owned_project(db, owner, project_id)
    interpreted = interpret_prompt(payload.prompt, _structured_from_create(payload), settings)
    from app.services.planning import _apply_spec

    _apply_spec(project, interpreted, db)
    project.schedule_stale = True
    record_change(db, project, "extracted", "Requirements were extracted again. The plan was not regenerated.")
    db.commit()
    db.refresh(project)
    return project_detail(db, project)


@router.post("/projects/{project_id}/generate")
def generate(
    project_id: str,
    payload: GenerateRequest,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    project = owned_project(db, owner, project_id)
    generate_project_plan(
        db,
        project,
        run_monte_carlo=False,
        seed=payload.seed,
        iterations=payload.iterations,
    )
    db.commit()
    if payload.run_monte_carlo:
        _launch(db, project, "monte_carlo", payload.seed, payload.iterations, None, payload.wait)
    db.refresh(project)
    return project_detail(db, project)


@router.post("/projects/{project_id}/tasks", status_code=201)
def add_task(
    project_id: str,
    payload: TaskCreate,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    project = owned_project(db, owner, project_id)
    if db.query(Task).filter(Task.project_id == project.id, Task.code == payload.code).first():
        api_error(409, "duplicate_task", "A task with that code already exists.")
    if payload.duration == 0 and not payload.milestone:
        api_error(422, "invalid_duration", "Zero duration is reserved for milestones.")
    row = Task(
        project_id=project.id,
        code=payload.code,
        wbs_code=payload.code,
        name=payload.name,
        description=payload.description,
        duration=payload.duration,
        duration_min=payload.duration_min,
        duration_mode=payload.duration_mode,
        duration_max=payload.duration_max,
        phase=payload.phase,
        is_milestone=payload.milestone,
        scalable=payload.scalable,
        sort_order=1000,
    )
    db.add(row)
    db.flush()
    for pred in payload.dependencies:
        predecessor = db.query(Task).filter(Task.project_id == project.id, Task.code == pred).one_or_none()
        if predecessor is None:
            api_error(422, "missing_dependency", f"Predecessor '{pred}' does not exist.")
        db.add(
            TaskDependency(
                project_id=project.id,
                predecessor_id=predecessor.id,
                successor_id=row.id,
                dependency_type="FS",
            )
        )
    project.schedule_stale = True
    record_change(db, project, "task_created", f"Task {payload.code} was added.")
    db.commit()
    return project_detail(db, project)


@router.patch("/projects/{project_id}/tasks/{task_id}")
def patch_task(
    project_id: str,
    task_id: str,
    payload: TaskUpdate,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    project = owned_project(db, owner, project_id)
    task = db.get(Task, task_id)
    if task is None or task.project_id != project.id:
        api_error(404, "not_found", "Task not found.")
    changes = payload.model_dump(exclude_unset=True)
    if "duration" in changes and changes["duration"] == 0 and not task.is_milestone:
        api_error(422, "invalid_duration", "Zero duration is reserved for milestones.")
    for key, value in changes.items():
        setattr(task, key, value)
    if any(key in changes for key in ("duration", "duration_min", "duration_mode", "duration_max", "phase")):
        project.schedule_stale = True
    record_change(db, project, "task_updated", f"Task {task.code} was edited.")
    db.commit()
    return project_detail(db, project)


@router.delete("/projects/{project_id}/tasks/{task_id}", status_code=204)
def delete_task(
    project_id: str,
    task_id: str,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> Response:
    project = owned_project(db, owner, project_id)
    task = db.get(Task, task_id)
    if task is None or task.project_id != project.id:
        api_error(404, "not_found", "Task not found.")
    db.query(TaskDependency).filter(
        (TaskDependency.predecessor_id == task.id) | (TaskDependency.successor_id == task.id)
    ).delete(synchronize_session=False)
    db.delete(task)
    project.schedule_stale = True
    record_change(db, project, "task_deleted", f"Task {task.code} was removed.")
    db.commit()
    return Response(status_code=204)


@router.post("/projects/{project_id}/dependencies", status_code=201)
def add_dependency(
    project_id: str,
    payload: DependencyCreate,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    project = owned_project(db, owner, project_id)
    if payload.dependency_type != "FS":
        api_error(422, "unsupported_dependency", "Only finish-to-start dependencies are implemented.")
    predecessor = db.query(Task).filter(Task.project_id == project.id, Task.code == payload.predecessor_code).one_or_none()
    successor = db.query(Task).filter(Task.project_id == project.id, Task.code == payload.successor_code).one_or_none()
    if predecessor is None or successor is None:
        api_error(422, "missing_task", "Both tasks must already exist in the project.")
    if predecessor.id == successor.id:
        api_error(422, "invalid_dependency", "A task cannot depend on itself.")
    db.add(
        TaskDependency(
            project_id=project.id,
            predecessor_id=predecessor.id,
            successor_id=successor.id,
            dependency_type="FS",
            lag_days=payload.lag_days,
        )
    )
    project.schedule_stale = True
    record_change(db, project, "dependency", f"Dependency {payload.predecessor_code} -> {payload.successor_code} added.")
    db.commit()
    return project_detail(db, project)


@router.delete("/projects/{project_id}/dependencies/{dependency_id}", status_code=204)
def delete_dependency(
    project_id: str,
    dependency_id: str,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> Response:
    project = owned_project(db, owner, project_id)
    dependency = db.get(TaskDependency, dependency_id)
    if dependency is None or dependency.project_id != project.id:
        api_error(404, "not_found", "Dependency not found.")
    db.delete(dependency)
    project.schedule_stale = True
    db.commit()
    return Response(status_code=204)


@router.post("/projects/{project_id}/costs", status_code=201)
def add_cost(
    project_id: str,
    payload: CostCreate,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    project = owned_project(db, owner, project_id)
    if payload.category not in COST_CATEGORIES:
        api_error(422, "invalid_category", "Cost category is not supported.")
    if payload.amount < 0 and payload.include_in_total:
        api_error(422, "negative_cost", "Included cost lines cannot be negative.")
    task_id = None
    if payload.task_code:
        task = db.query(Task).filter(Task.project_id == project.id, Task.code == payload.task_code).one_or_none()
        if task is None:
            api_error(422, "missing_task", "The cost line's task code does not exist.")
        task_id = task.id
    db.add(
        CostItem(
            project_id=project.id,
            task_id=task_id,
            code=payload.code,
            name=payload.name,
            category=payload.category,
            amount=payload.amount,
            phase=payload.phase,
            include_in_total=payload.include_in_total,
            source=payload.source,
            source_date=payload.source_date,
            notes=payload.notes,
            quantity=payload.quantity,
            unit=payload.unit,
            unit_cost=payload.amount / payload.quantity if payload.quantity else payload.amount,
        )
    )
    record_change(db, project, "cost", f"Cost line {payload.code} was added.")
    db.commit()
    return project_detail(db, project)


@router.post("/projects/{project_id}/schedule")
def schedule(
    project_id: str,
    payload: ScheduleRequest,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    project = owned_project(db, owner, project_id)
    try:
        run = execute_simulation(
            db,
            project,
            run_type="deterministic",
            seed=None,
            iterations=None,
            scenario=None,
            set_baseline=payload.set_baseline,
        )
    except ValueError as exc:
        db.commit()
        api_error(422, "schedule_failed", str(exc))
    db.commit()
    return run_payload(run)


@router.post("/projects/{project_id}/budget")
def budget(project_id: str, owner: str = Depends(get_owner), db: Session = Depends(get_db)) -> dict:
    project = owned_project(db, owner, project_id)
    detail = project_detail(db, project)
    if detail["cost_summary"] is None:
        api_error(422, "missing_costs", "The project has no cost lines.")
    return detail["cost_summary"]


@router.post("/projects/{project_id}/resources")
def resources(project_id: str, owner: str = Depends(get_owner), db: Session = Depends(get_db)) -> dict:
    project = owned_project(db, owner, project_id)
    snapshot = snapshot_from_project(db, project)
    if not snapshot["tasks"]:
        api_error(422, "missing_plan", "Generate a plan before analyzing resources.")
    try:
        payload = evaluate_snapshot(snapshot)
    except ValueError as exc:
        api_error(422, "schedule_failed", str(exc))
    return {
        "conflicts": payload["resource_conflicts"],
        "peaks": payload["resource_peaks"],
        "assumptions": payload["assumptions"],
    }


@router.post("/projects/{project_id}/risks")
def risks(project_id: str, owner: str = Depends(get_owner), db: Session = Depends(get_db)) -> dict:
    project = owned_project(db, owner, project_id)
    detail = project_detail(db, project)
    return {"risks": detail["risks"], "validation": detail["validation"]}


def _launch(db: Session, project: Project, run_type: str, seed: int | None, iterations: int | None, scenario, wait: bool) -> SimulationRun:
    try:
        run = queue_simulation(
            db,
            project,
            run_type=run_type,
            seed=seed,
            iterations=iterations,
            scenario=scenario,
        )
    except ValueError as exc:
        api_error(422, "simulation_failed", str(exc))
    db.commit()
    submit_run(run.id, wait=wait)
    db.expire_all()
    stored = db.get(SimulationRun, run.id)
    if stored is None:
        api_error(500, "simulation_missing", "The simulation run could not be reloaded.")
    if wait and stored.status == "failed":
        api_error(422, "simulation_failed", stored.error_message or "Simulation failed.", {"run_id": stored.id})
    return stored


@router.post("/projects/{project_id}/simulations", status_code=201)
def simulate(
    project_id: str,
    payload: SimulationRequest,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    project = owned_project(db, owner, project_id)
    if payload.run_type not in {"deterministic", "monte_carlo"}:
        api_error(422, "invalid_run_type", "run_type must be deterministic or monte_carlo.")
    scenario = None
    if payload.scenario_id:
        scenario = db.get(Scenario, payload.scenario_id)
        if scenario is None or scenario.project_id != project.id:
            api_error(404, "not_found", "Scenario not found.")
    seed = payload.seed if payload.run_type == "monte_carlo" else None
    iterations = payload.iterations if payload.run_type == "monte_carlo" else None
    run = _launch(db, project, payload.run_type, seed, iterations, scenario, payload.wait)
    record_change(db, project, "simulated", f"{payload.run_type} simulation {run.status}.")
    db.commit()
    return run_payload(run, include_samples=False)


@router.get("/projects/{project_id}/simulations")
def list_simulations(
    project_id: str,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    project = owned_project(db, owner, project_id)
    query = db.query(SimulationRun).filter(SimulationRun.project_id == project.id)
    total = query.count()
    rows = query.order_by(SimulationRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [run_payload(row) for row in rows], "page": page, "page_size": page_size, "total": total}


@router.get("/projects/{project_id}/simulations/{run_id}")
def get_simulation(
    project_id: str,
    run_id: str,
    include_samples: bool = False,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    project = owned_project(db, owner, project_id)
    run = db.get(SimulationRun, run_id)
    if run is None or run.project_id != project.id:
        api_error(404, "not_found", "Simulation run not found.")
    return run_payload(run, include_samples=include_samples)


@router.post("/projects/{project_id}/scenarios", status_code=201)
def add_scenario(
    project_id: str,
    payload: ScenarioCreate,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
) -> dict:
    project = owned_project(db, owner, project_id)
    raw = payload.model_dump()
    try:
        patch = patch_from_payload(raw)
        scenario, _notes = create_scenario(db, project, patch, raw)
        db.commit()
        db.refresh(scenario)
        if payload.run:
            _launch(db, project, "deterministic", None, None, scenario, payload.wait)
            if payload.monte_carlo:
                _launch(db, project, "monte_carlo", payload.seed, payload.iterations, scenario, payload.wait)
    except ValueError as exc:
        db.rollback()
        api_error(422, "invalid_scenario", str(exc))
    db.refresh(scenario)
    return scenario_payload(db, scenario)


@router.get("/projects/{project_id}/scenarios")
def list_scenarios(project_id: str, owner: str = Depends(get_owner), db: Session = Depends(get_db)) -> dict:
    project = owned_project(db, owner, project_id)
    return {"items": [scenario_payload(db, row) for row in project.scenarios]}


@router.post("/projects/{project_id}/scenarios/compare")
def compare_scenarios(project_id: str, owner: str = Depends(get_owner), db: Session = Depends(get_db)) -> dict:
    project = owned_project(db, owner, project_id)
    baseline = latest_run(db, project.id, "deterministic")
    baseline_mc = latest_run(db, project.id, "monte_carlo")
    base_result = baseline.result.payload if baseline and baseline.result else None
    if base_result is None:
        api_error(422, "missing_baseline", "Run the baseline simulation before comparing scenarios.")
    rows = []
    for scenario in project.scenarios:
        item = scenario_payload(db, scenario)
        det = (item.get("deterministic") or {}).get("result") or {}
        mc = (item.get("monte_carlo") or {}).get("result") or {}
        duration = det.get("project_duration")
        cost = det.get("total_cost")
        rows.append(
            {
                "scenario_id": scenario.id,
                "name": scenario.name,
                "description": scenario.description,
                "input_changes": scenario.notes,
                "patch": scenario.patch,
                "duration": duration,
                "duration_delta": None if duration is None else duration - base_result["project_duration"],
                "total_cost": cost,
                "cost_delta": None if cost is None else cost - base_result["total_cost"],
                "critical_path": det.get("critical_path"),
                "baseline_critical_path": base_result.get("critical_path"),
                "resource_conflicts": det.get("resource_conflicts"),
                "deadline_probability": mc.get("deadline_probability"),
                "budget_probability": mc.get("budget_probability"),
                "simulated": bool(det),
            }
        )
    base_mc = baseline_mc.result.payload if baseline_mc and baseline_mc.result else {}
    return {
        "baseline": {
            "run_id": baseline.id,
            "duration": base_result["project_duration"],
            "total_cost": base_result["total_cost"],
            "critical_path": base_result.get("critical_path"),
            "deadline_probability": base_mc.get("deadline_probability"),
            "budget_probability": base_mc.get("budget_probability"),
            "resource_conflicts": base_result.get("resource_conflicts"),
        },
        "scenarios": rows,
        "disclaimer": "Deltas compare independent scenario snapshots with the baseline run. They are model differences, not forecasts of a real project.",
    }


@router.post("/projects/{project_id}/reports")
def create_report(
    project_id: str,
    payload: ReportRequest,
    owner: str = Depends(get_owner),
    db: Session = Depends(get_db),
):
    project = owned_project(db, owner, project_id)
    document = collect_document(db, project)
    try:
        body, media, filename = render_report(document, payload.format, payload.report_type)
    except ValueError as exc:
        api_error(422, "invalid_report", str(exc))
    row = store_report(db, project, payload.format, payload.report_type, filename, document)
    db.commit()
    return Response(
        content=body,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Id": row.id,
        },
    )


@router.get("/projects/{project_id}/reports")
def list_reports(project_id: str, owner: str = Depends(get_owner), db: Session = Depends(get_db)) -> dict:
    project = owned_project(db, owner, project_id)
    return {
        "items": [
            {
                "id": row.id,
                "format": row.format,
                "report_type": row.report_type,
                "filename": row.filename,
                "metadata": row.metadata_json,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in project.reports
        ]
    }


@router.get("/projects/{project_id}/history")
def history(project_id: str, owner: str = Depends(get_owner), db: Session = Depends(get_db)) -> dict:
    project = owned_project(db, owner, project_id)
    rows = (
        db.query(ProjectChange)
        .filter(ProjectChange.project_id == project.id)
        .order_by(ProjectChange.created_at.desc())
        .limit(100)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "change_type": row.change_type,
                "summary": row.summary,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }


@router.post("/demo/residential-tower", status_code=201)
def demo(owner: str = Depends(get_owner), db: Session = Depends(get_db)) -> dict:
    project = seed_residential_demo(db, owner)
    return project_detail(db, project)
