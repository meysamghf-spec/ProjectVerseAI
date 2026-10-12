"""Cost aggregation.

Parent rollups and explanatory resource rates must not be added on top of the
leaf cost lines that already contain those amounts. Only lines with
`include_in_total` participate in the project total.
"""

from __future__ import annotations

from app.engine.types import BudgetResult, CostLine

COST_CATEGORIES = (
    "labor",
    "materials",
    "equipment",
    "services",
    "overhead",
    "contingency",
    "other",
)


def aggregate_costs(lines: list[CostLine], budget: float | None = None) -> BudgetResult:
    errors: list[str] = []
    for line in lines:
        if line.amount < 0 and line.include_in_total:
            errors.append(f"Cost line '{line.id}' has a negative amount.")
        if line.category not in COST_CATEGORIES:
            errors.append(
                f"Cost line '{line.id}' uses unknown category '{line.category}'."
            )
    if errors:
        raise ValueError("; ".join(errors))

    included = [line for line in lines if line.include_in_total]
    excluded = [line for line in lines if not line.include_in_total]
    total = sum(line.amount for line in included)
    by_category = {category: 0.0 for category in COST_CATEGORIES}
    by_phase: dict[str, float] = {}
    by_task: dict[str, float] = {}
    for line in included:
        by_category[line.category] = by_category.get(line.category, 0.0) + line.amount
        phase = line.phase or "unassigned"
        by_phase[phase] = by_phase.get(phase, 0.0) + line.amount
        if line.task_id:
            by_task[line.task_id] = by_task.get(line.task_id, 0.0) + line.amount

    variance = None if budget is None else budget - total
    overrun = budget is not None and total - budget > 1e-6
    assumptions = [
        "The total is the sum of cost lines marked include_in_total.",
        "Lines marked as rollups are excluded so parent and child amounts are not both counted.",
        "No live market prices are fetched. Sample or user-supplied unit costs keep their source labels.",
        "A positive variance means the estimate is under the stated budget. It is not a bid.",
    ]
    return BudgetResult(
        total=total,
        budget=budget,
        variance=variance,
        overrun=overrun,
        by_category=by_category,
        by_phase=by_phase,
        by_task=by_task,
        included_line_ids=[line.id for line in included],
        excluded_line_ids=[line.id for line in excluded],
        assumptions=assumptions,
    )
