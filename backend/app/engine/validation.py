"""Plan checks. Warnings do not by themselves block a simulation."""

from __future__ import annotations

from datetime import date

from app.engine.scheduler import schedule_tasks
from app.engine.types import CostLine, ResourcePool, SchedTask, WorkCalendar


def validate_plan(
    tasks: list[SchedTask],
    costs: list[CostLine],
    pools: list[ResourcePool],
    *,
    start: date | None = None,
    deadline: date | None = None,
    budget: float | None = None,
    calendar: WorkCalendar | None = None,
    assumptions_present: bool = True,
) -> dict:
    warnings: list[str] = []
    errors: list[str] = []
    schedule = schedule_tasks(tasks, calendar=calendar, project_start=start)
    errors.extend(schedule.errors)
    warnings.extend(schedule.warnings)

    for line in costs:
        if line.include_in_total and line.amount < 0:
            errors.append(f"Negative cost on line '{line.id}'.")

    if start and deadline and deadline < start:
        errors.append("The deadline is earlier than the start date.")

    total = sum(line.amount for line in costs if line.include_in_total)
    if budget is not None and total - budget > 1e-6:
        warnings.append(
            f"Estimated cost {total:.2f} exceeds the stated budget {budget:.2f}. "
            "This is a model comparison, not an invoice."
        )
    if deadline and start and schedule.ok:
        # Deadline variance uses the exclusive project finish offset mapped by
        # the same calendar-day count the scheduler already computed.
        duration_days = (deadline - start).days
        if schedule.project_duration - duration_days > 1e-6:
            warnings.append(
                f"Critical-path duration {schedule.project_duration:g} days runs past the "
                f"{duration_days}-day window between start and deadline."
            )

    if schedule.ok:
        from app.engine.resources import analyze_resources

        resources = analyze_resources(schedule.tasks, tasks, pools)
        warnings.extend(resources.conflicts)

    if not assumptions_present:
        warnings.append("No planning assumptions were recorded.")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "can_continue": True,
        "schedule_ok": schedule.ok,
        "project_duration": schedule.project_duration if schedule.ok else None,
        "critical_path": schedule.critical_path if schedule.ok else [],
    }
