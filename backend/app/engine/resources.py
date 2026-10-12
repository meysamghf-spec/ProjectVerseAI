"""Resource demand over the scheduled timeline.

Demand is counted on half-open day buckets [start, finish). A task that
finishes when the next task starts does not double-book the boundary day.
"""

from __future__ import annotations

import math

from app.engine.types import ResourceLoad, ResourcePool, ResourceResult, SchedTask, ScheduledTask


def analyze_resources(
    scheduled: list[ScheduledTask],
    tasks: list[SchedTask],
    pools: list[ResourcePool],
) -> ResourceResult:
    by_id = {task.id: task for task in tasks}
    loads = {
        pool.id: {
            "name": pool.name,
            "available": pool.available,
            "days": {},
        }
        for pool in pools
    }
    assumptions = [
        "Resource demand is the sum of assignments whose tasks overlap on a day.",
        "Availability is constant across the project. Calendars do not yet vary by resource.",
        "An overload is demand greater than availability on at least one day.",
        "Adding people does not by itself change durations. Duration effects belong to scenario factors.",
    ]
    conflicts: list[str] = []
    unknown: list[str] = []

    for item in scheduled:
        source = by_id.get(item.id)
        if source is None:
            continue
        start = int(math.floor(item.earliest_start + 1e-9))
        finish = int(math.ceil(item.earliest_finish - 1e-9))
        if finish <= start:
            continue
        for demand in source.resources:
            bucket = loads.get(demand.resource_id)
            if bucket is None:
                unknown.append(demand.resource_id)
                continue
            for day in range(start, finish):
                bucket["days"][day] = bucket["days"].get(day, 0.0) + demand.quantity

    results = []
    for pool in pools:
        bucket = loads[pool.id]
        days: dict[int, float] = bucket["days"]
        peak = max(days.values(), default=0.0)
        overloaded = peak - pool.available > 1e-6
        if overloaded:
            hot_days = [day for day, qty in sorted(days.items()) if qty - pool.available > 1e-6]
            preview = ", ".join(str(day) for day in hot_days[:8])
            conflicts.append(
                f"{pool.name} peaks at {peak:g} {pool.unit} against availability {pool.available:g} "
                f"on day offset(s) {preview}."
            )
        results.append(
            {
                "resource_id": pool.id,
                "name": pool.name,
                "available": pool.available,
                "peak": peak,
                "overloaded": overloaded,
                "demand_by_day": {int(day): qty for day, qty in sorted(days.items())},
            }
        )

    if unknown:
        names = ", ".join(sorted(set(unknown)))
        conflicts.append(f"Tasks reference unknown resources: {names}.")

    return ResourceResult(
        resources=[
            ResourceLoad(
                resource_id=item["resource_id"],
                name=item["name"],
                available=item["available"],
                peak=item["peak"],
                overloaded=item["overloaded"],
                demand_by_day=item["demand_by_day"],
            )
            for item in results
        ],
        conflicts=conflicts,
        assumptions=assumptions,
    )
