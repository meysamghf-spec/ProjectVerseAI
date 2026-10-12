"""Gantt rows and planned expenditure curves derived from a schedule."""

from __future__ import annotations

import math

from app.engine.types import ScheduledTask


def gantt_rows(scheduled: list[ScheduledTask]) -> list[dict]:
    return [
        {
            "id": task.id,
            "name": task.name,
            "phase": task.phase,
            "start": task.earliest_start,
            "finish": task.earliest_finish,
            "duration": task.duration,
            "total_float": task.total_float,
            "critical": task.is_critical,
            "milestone": task.milestone,
            "dependencies": list(task.dependencies),
            "start_date": task.start_date.isoformat() if task.start_date else None,
            "finish_date": task.finish_date.isoformat() if task.finish_date else None,
        }
        for task in scheduled
    ]


def cumulative_cost(
    scheduled: list[ScheduledTask],
    phase_costs: dict[str, float],
) -> list[dict]:
    """Spread each phase cost evenly across that phase's scheduled span.

    Costs with no matching phase are spread across the whole project. The
    curve is planned value, not actual expenditure.
    """

    duration = max((task.earliest_finish for task in scheduled), default=0.0)
    total = sum(phase_costs.values())
    if duration <= 1e-9:
        return [{"day": 0, "cost": round(total, 2)}]

    days = max(int(math.ceil(duration - 1e-9)), 1)
    buckets = [0.0] * days
    for phase, amount in phase_costs.items():
        if abs(amount) <= 1e-12:
            continue
        members = [task for task in scheduled if task.phase == phase and task.earliest_finish > task.earliest_start]
        if members:
            start = min(task.earliest_start for task in members)
            finish = max(task.earliest_finish for task in members)
        else:
            start, finish = 0.0, float(days)
        start_i = min(days - 1, max(0, int(math.floor(start + 1e-9))))
        finish_i = min(days, max(start_i + 1, int(math.ceil(finish - 1e-9))))
        per_day = amount / (finish_i - start_i)
        for index in range(start_i, finish_i):
            buckets[index] += per_day

    running = 0.0
    points = []
    for index, value in enumerate(buckets):
        running += value
        points.append({"day": index + 1, "cost": round(running, 2)})
    if points:
        points[-1]["cost"] = round(total, 2)
    return points
