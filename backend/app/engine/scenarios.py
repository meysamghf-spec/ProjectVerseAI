"""Scenario patches.

A patch returns new task and cost lists. The caller's baseline objects are
not modified. Extra workers change duration only where a factor is configured
and, when requested, only on tasks marked scalable.
"""

from __future__ import annotations

from dataclasses import replace

from app.engine.types import CostLine, ScenarioPatch, SchedTask


def apply_scenario(
    tasks: list[SchedTask],
    costs: list[CostLine],
    patch: ScenarioPatch,
) -> tuple[list[SchedTask], list[CostLine], list[str]]:
    notes = list(patch.notes)
    removed = set(patch.remove_task_ids)
    cloned: list[SchedTask] = []
    for task in tasks:
        if task.id in removed:
            notes.append(f"Removed task {task.id}.")
            continue
        factor = _duration_factor(task, patch)
        duration = task.duration
        if factor != 1:
            duration = round(task.duration * factor, 4)
            notes.append(
                f"{task.id} duration multiplied by {factor:g} "
                f"({'scalable task' if task.scalable else 'explicit factor'})."
            )
        dependencies = [dep for dep in task.dependencies if dep not in removed and (task.id, dep) not in set(patch.remove_dependencies)]
        lags = {dep: task.lags.get(dep, 0.0) for dep in dependencies}
        for pred, lag in patch.extra_lags.items():
            if pred in dependencies:
                lags[pred] = lags.get(pred, 0.0) + lag
                notes.append(f"Added {lag:g} days of lag from {pred} to {task.id}.")
        cloned.append(
            replace(
                task,
                duration=0.0 if task.milestone else duration,
                dependencies=dependencies,
                lags=lags,
                duration_min=None if task.duration_min is None else round(task.duration_min * factor, 4),
                duration_mode=None if task.duration_mode is None else round((task.duration_mode or duration) * factor, 4),
                duration_max=None if task.duration_max is None else round(task.duration_max * factor, 4),
                resources=list(task.resources),
            )
        )

    existing = {task.id for task in cloned}
    for successor, predecessor, lag in patch.add_dependencies:
        if successor in existing and predecessor in existing:
            for task in cloned:
                if task.id == successor and predecessor not in task.dependencies:
                    task.dependencies.append(predecessor)
                    task.lags[predecessor] = lag
                    notes.append(f"Added dependency {predecessor} -> {successor} with lag {lag:g}.")
    for successor, predecessor, lag in patch.lag_overrides:
        for task in cloned:
            if task.id == successor and predecessor in task.dependencies:
                task.lags[predecessor] = lag
                notes.append(
                    f"Set lag from {predecessor} to {successor} to {lag:g} days "
                    "(negative lag overlaps the predecessor)."
                )

    # Drop dependencies that point at removed tasks.
    for task in cloned:
        task.dependencies = [dep for dep in task.dependencies if dep in existing]

    next_costs: list[CostLine] = []
    for line in costs:
        if line.task_id and line.task_id in removed:
            continue
        factor = patch.cost_category_factors.get(line.category, 1.0)
        if factor != 1 and line.include_in_total and line.category not in {"overhead", "contingency"}:
            notes.append(f"Cost category {line.category} multiplied by {factor:g} on line {line.id}.")
        amount = round(line.amount * factor, 2) if line.category not in {"overhead", "contingency"} else line.amount
        # Overhead and contingency are recomputed by the caller from the cost model
        # when category factors change. Keep them out of the scaled set here.
        next_costs.append(
            replace(
                line,
                amount=amount,
                amount_min=None if line.amount_min is None else round(line.amount_min * (factor if line.category not in {'overhead', 'contingency'} else 1), 2),
                amount_mode=None if line.amount_mode is None else round((line.amount_mode or line.amount) * (factor if line.category not in {'overhead', 'contingency'} else 1), 2),
                amount_max=None if line.amount_max is None else round(line.amount_max * (factor if line.category not in {'overhead', 'contingency'} else 1), 2),
            )
        )
    if patch.cost_category_factors:
        notes.append(
            "Overhead and contingency percentages are reapplied from the cost model after category scaling."
        )
    notes.append("Adding workers does not shorten tasks unless this scenario sets a duration factor.")
    return cloned, next_costs, notes


def _duration_factor(task: SchedTask, patch: ScenarioPatch) -> float:
    if task.id in patch.duration_factors:
        return patch.duration_factors[task.id]
    if task.phase in patch.duration_factors and (not patch.scalable_only or task.scalable):
        if patch.scalable_only and patch.scalable_phases and task.phase not in patch.scalable_phases:
            return 1.0
        return patch.duration_factors[task.phase]
    if patch.scalable_only and task.scalable and task.phase in patch.scalable_phases:
        return patch.duration_factors.get(task.phase, 1.0)
    return 1.0


def recompute_percent_costs(lines: list[CostLine], overhead_pct: float, contingency_pct: float) -> list[CostLine]:
    """Replace overhead and contingency using the current direct total."""

    direct = sum(
        line.amount
        for line in lines
        if line.include_in_total and line.category not in {"overhead", "contingency"}
    )
    overhead = round(direct * overhead_pct, 2)
    contingency = round((direct + overhead) * contingency_pct, 2)
    updated: list[CostLine] = []
    saw_overhead = False
    saw_contingency = False
    for line in lines:
        if line.category == "overhead":
            amount = overhead if not saw_overhead else 0.0
            saw_overhead = True
            updated.append(replace(line, amount=amount, amount_min=amount, amount_mode=amount, amount_max=amount))
        elif line.category == "contingency":
            amount = contingency if not saw_contingency else 0.0
            saw_contingency = True
            updated.append(replace(line, amount=amount, amount_min=amount, amount_mode=amount, amount_max=amount))
        else:
            updated.append(line)
    return updated
