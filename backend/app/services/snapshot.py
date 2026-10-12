"""Convert between stored plans and engine inputs.

Scenario snapshots are independent copies. Simulating a scenario does not
write dates back onto the baseline tasks.
"""

from __future__ import annotations

from datetime import date

from app.engine.budget import aggregate_costs
from app.engine.curves import cumulative_cost, gantt_rows
from app.engine.monte_carlo import CostModel, run_monte_carlo
from app.engine.resources import analyze_resources
from app.engine.scheduler import schedule_tasks
from app.engine.types import CostLine, ResourceDemand, ResourcePool, SchedTask, WorkCalendar
from app.engine.validation import validate_plan


def calendar_from_dict(raw: dict | None) -> WorkCalendar:
    raw = raw or {}
    holidays = []
    for value in raw.get("holiday_dates") or []:
        holidays.append(date.fromisoformat(value))
    return WorkCalendar(
        skip_weekends=bool(raw.get("skip_weekends", False)),
        hours_per_day=float(raw.get("hours_per_day") or 8),
        days_per_week=int(raw.get("days_per_week") or 7),
        holiday_dates=holidays,
    )


def task_from_dict(raw: dict) -> SchedTask:
    return SchedTask(
        id=raw["id"],
        name=raw["name"],
        duration=float(raw["duration"]),
        dependencies=list(raw.get("dependencies") or []),
        lags={key: float(value) for key, value in (raw.get("lags") or {}).items()},
        milestone=bool(raw.get("milestone") or raw.get("is_milestone")),
        scalable=bool(raw.get("scalable")),
        phase=raw.get("phase") or "",
        wbs_code=raw.get("wbs_code") or raw["id"],
        description=raw.get("description") or "",
        cost=float(raw.get("cost") or 0),
        duration_min=raw.get("duration_min"),
        duration_mode=raw.get("duration_mode"),
        duration_max=raw.get("duration_max"),
        resources=[
            ResourceDemand(item["resource_id"], float(item["quantity"]))
            for item in raw.get("resources") or []
        ],
        progress=float(raw.get("progress") or 0),
        status=raw.get("status") or "not_started",
    )


def cost_from_dict(raw: dict) -> CostLine:
    return CostLine(
        id=raw["code"] if "code" in raw else raw["id"],
        name=raw["name"],
        category=raw["category"],
        amount=float(raw["amount"]),
        task_id=raw.get("task_code") or raw.get("task_id"),
        phase=raw.get("phase"),
        include_in_total=bool(raw.get("include_in_total", True)),
        source=raw.get("source") or "assumption",
        source_date=raw.get("source_date"),
        notes=raw.get("notes") or "",
        amount_min=raw.get("amount_min"),
        amount_mode=raw.get("amount_mode"),
        amount_max=raw.get("amount_max"),
        quantity=float(raw.get("quantity") or 1),
        unit=raw.get("unit") or "lump_sum",
        unit_cost=float(raw.get("unit_cost") or 0),
    )


def pool_from_dict(raw: dict) -> ResourcePool:
    return ResourcePool(
        id=raw["code"] if "code" in raw else raw["id"],
        name=raw["name"],
        available=float(raw["available"]),
        resource_type=raw.get("resource_type") or "labor",
        unit=raw.get("unit") or "person",
        rate=float(raw.get("rate") or 0),
    )


def cost_model_from(snapshot: dict) -> CostModel:
    meta = snapshot.get("cost_model") or {}
    direct_ids = set(meta.get("direct_line_ids") or [])
    lines = []
    for raw in snapshot.get("costs") or []:
        line = cost_from_dict(raw)
        if not line.include_in_total:
            continue
        if line.category in {"overhead", "contingency"}:
            continue
        if direct_ids and line.id not in direct_ids:
            continue
        lines.append(line)
    return CostModel(
        overhead_pct=float(meta.get("overhead_pct") or 0),
        contingency_pct=float(meta.get("contingency_pct") or 0),
        direct_lines=lines,
    )


def evaluate_snapshot(snapshot: dict) -> dict:
    tasks = [task_from_dict(item) for item in snapshot.get("tasks") or []]
    costs = [cost_from_dict(item) for item in snapshot.get("costs") or []]
    pools = [pool_from_dict(item) for item in snapshot.get("resources") or []]
    calendar = calendar_from_dict(snapshot.get("calendar"))
    start = date.fromisoformat(snapshot["start_date"]) if snapshot.get("start_date") else None
    schedule = schedule_tasks(tasks, calendar=calendar, project_start=start)
    if not schedule.ok:
        raise ValueError("; ".join(schedule.errors))
    budget = aggregate_costs(costs, snapshot.get("budget"))
    resources = analyze_resources(schedule.tasks, tasks, pools)
    checks = validate_plan(
        tasks,
        costs,
        pools,
        start=start,
        deadline=_deadline_date(snapshot),
        budget=snapshot.get("budget"),
        calendar=calendar,
    )
    deadline_variance = None
    if snapshot.get("deadline_day") is not None:
        deadline_variance = schedule.project_duration - float(snapshot["deadline_day"])
    completion = None
    if schedule.tasks and start is not None:
        finishes = [task.exclusive_finish_date for task in schedule.tasks if task.exclusive_finish_date]
        if finishes:
            completion = max(finishes).isoformat()
    scheduled_by_id = {task.id: task for task in schedule.tasks}
    baseline_rows = []
    for raw in snapshot.get("tasks") or []:
        scheduled = scheduled_by_id.get(raw["id"])
        if scheduled is None or raw.get("baseline_finish") is None:
            continue
        baseline_rows.append(
            {
                "id": scheduled.id,
                "baseline_finish": raw["baseline_finish"],
                "finish": scheduled.earliest_finish,
                "finish_variance": scheduled.earliest_finish - float(raw["baseline_finish"]),
            }
        )
    return {
        "kind": "deterministic",
        "project_duration": schedule.project_duration,
        "critical_path": schedule.critical_path,
        "critical_tasks": schedule.critical_tasks,
        "completion_date": completion,
        "total_cost": budget.total,
        "budget": budget.budget,
        "budget_variance": budget.variance,
        "budget_overrun": budget.overrun,
        "by_category": budget.by_category,
        "by_phase": budget.by_phase,
        "by_task": budget.by_task,
        "gantt": gantt_rows(schedule.tasks),
        "cumulative_cost": cumulative_cost(schedule.tasks, budget.by_phase),
        "resource_conflicts": resources.conflicts,
        "resource_peaks": [
            {
                "id": item.resource_id,
                "name": item.name,
                "peak": item.peak,
                "available": item.available,
                "overloaded": item.overloaded,
                "demand_by_day": {str(day): qty for day, qty in item.demand_by_day.items()},
            }
            for item in resources.resources
        ],
        "warnings": checks["warnings"],
        "errors": checks["errors"],
        "assumptions": schedule.assumptions + budget.assumptions + resources.assumptions,
        "deadline_variance_days": deadline_variance,
        "baseline_comparison": baseline_rows,
        "schedule": [
            {
                "id": task.id,
                "earliest_start": task.earliest_start,
                "earliest_finish": task.earliest_finish,
                "latest_start": task.latest_start,
                "latest_finish": task.latest_finish,
                "total_float": task.total_float,
                "is_critical": task.is_critical,
                "start_date": task.start_date.isoformat() if task.start_date else None,
                "finish_date": task.finish_date.isoformat() if task.finish_date else None,
            }
            for task in schedule.tasks
        ],
        "p50_duration": None,
        "p80_duration": None,
        "p90_duration": None,
        "p50_cost": None,
        "p80_cost": None,
        "p90_cost": None,
        "deadline_probability": None,
        "budget_probability": None,
        "schedule_contributors": [],
        "cost_contributors": [],
        "disclaimer": (
            "Deterministic model output from stored inputs and sample assumptions. "
            "Not a verified quotation, schedule, or engineering result."
        ),
    }


def evaluate_monte_carlo(snapshot: dict, seed: int, iterations: int) -> dict:
    tasks = [task_from_dict(item) for item in snapshot.get("tasks") or []]
    calendar = calendar_from_dict(snapshot.get("calendar"))
    outcome = run_monte_carlo(
        tasks,
        seed=seed,
        iterations=iterations,
        calendar=calendar,
        cost_model=cost_model_from(snapshot),
        deadline_day=snapshot.get("deadline_day"),
        budget=snapshot.get("budget"),
    )
    payload = evaluate_snapshot(snapshot)
    payload["kind"] = "monte_carlo"
    payload["seed"] = outcome.seed
    payload["iterations"] = outcome.iterations
    payload["p50_duration"] = outcome.p50_duration
    payload["p80_duration"] = outcome.p80_duration
    payload["p90_duration"] = outcome.p90_duration
    payload["p50_cost"] = outcome.p50_cost
    payload["p80_cost"] = outcome.p80_cost
    payload["p90_cost"] = outcome.p90_cost
    payload["deadline_probability"] = outcome.deadline_probability
    payload["budget_probability"] = outcome.budget_probability
    payload["schedule_contributors"] = outcome.schedule_contributors
    payload["cost_contributors"] = outcome.cost_contributors
    payload["duration_samples"] = outcome.duration_samples
    payload["cost_samples"] = outcome.cost_samples
    payload["warnings"] = list(payload["warnings"]) + list(outcome.warnings)
    payload["assumptions"] = list(payload["assumptions"]) + list(outcome.assumptions)
    payload["deterministic_duration"] = outcome.deterministic_duration
    payload["deterministic_cost"] = outcome.deterministic_cost
    payload["disclaimer"] = (
        "Probabilistic results are percentiles of seeded samples from this model. "
        "They are not confidence intervals from historical project data."
    )
    return payload


def _deadline_date(snapshot: dict):
    if snapshot.get("start_date") and snapshot.get("deadline_day") is not None:
        from datetime import timedelta

        return date.fromisoformat(snapshot["start_date"]) + timedelta(days=float(snapshot["deadline_day"]))
    return None
