"""Critical-path scheduler.

The scheduler uses finish-to-start dependencies. A task's earliest start is the
maximum exclusive finish of its predecessors, plus any lag. Independent tasks
start together at offset 0. Duration is not the same thing as elapsed calendar
time when a work calendar skips non-working days; the numeric CPM network is
computed in duration units, and dates are projected afterwards.
"""

from __future__ import annotations

from app.engine.calendar import add_days, inclusive_finish
from app.engine.types import SchedTask, ScheduledTask, ScheduleResult, WorkCalendar

_EPS = 1e-6


def _validate(tasks: list[SchedTask]) -> tuple[list[str], list[str], dict[str, SchedTask]]:
    errors: list[str] = []
    warnings: list[str] = []
    by_id: dict[str, SchedTask] = {}
    for task in tasks:
        if task.id in by_id:
            errors.append(f"Duplicate task id '{task.id}'.")
            continue
        by_id[task.id] = task
        if task.duration < -_EPS:
            errors.append(f"Task '{task.id}' has a negative duration.")
        elif task.duration <= _EPS and not task.milestone:
            errors.append(
                f"Task '{task.id}' has zero duration but is not marked as a milestone."
            )
        if task.milestone and task.duration > _EPS:
            warnings.append(
                f"Milestone '{task.id}' has a non-zero duration; it is scheduled as a task."
            )
        if task.cost < -_EPS:
            errors.append(f"Task '{task.id}' has a negative cost.")
        for pred in task.dependencies:
            if pred == task.id:
                errors.append(f"Task '{task.id}' depends on itself.")
    for task in tasks:
        for pred in task.dependencies:
            if pred not in by_id:
                errors.append(f"Task '{task.id}' depends on missing task '{pred}'.")
    return errors, warnings, by_id


def _find_cycle(by_id: dict[str, SchedTask]) -> list[str] | None:
    color = {task_id: 0 for task_id in by_id}
    stack: list[str] = []

    def visit(task_id: str) -> list[str] | None:
        color[task_id] = 1
        stack.append(task_id)
        for pred in by_id[task_id].dependencies:
            if pred not in by_id:
                continue
            if color[pred] == 1:
                cycle = stack[stack.index(pred) :] + [pred]
                return cycle
            if color[pred] == 0:
                found = visit(pred)
                if found:
                    return found
        stack.pop()
        color[task_id] = 2
        return None

    for task_id in by_id:
        if color[task_id] == 0:
            found = visit(task_id)
            if found:
                return found
    return None


def _topo(by_id: dict[str, SchedTask]) -> list[str]:
    indegree = {task_id: 0 for task_id in by_id}
    successors: dict[str, list[str]] = {task_id: [] for task_id in by_id}
    for task in by_id.values():
        for pred in task.dependencies:
            if pred in by_id:
                indegree[task.id] += 1
                successors[pred].append(task.id)
    queue = sorted([task_id for task_id, degree in indegree.items() if degree == 0])
    order: list[str] = []
    while queue:
        current = queue.pop(0)
        order.append(current)
        for succ in successors[current]:
            indegree[succ] -= 1
            if indegree[succ] == 0:
                queue.append(succ)
        queue.sort()
    return order


def schedule_tasks(
    tasks: list[SchedTask],
    calendar: WorkCalendar | None = None,
    project_start=None,
) -> ScheduleResult:
    """Compute earliest/latest dates, float, and one critical path.

    `project_start` is a datetime.date. When omitted, only day offsets are returned.
    """

    calendar = calendar or WorkCalendar()
    errors, warnings, by_id = _validate(tasks)
    assumptions = calendar.assumption_notes() + [
        "Dependencies are finish-to-start.",
        "Parallel tasks start on the same offset when neither waits on the other.",
        "Total float is latest start minus earliest start.",
        "A task is critical when its total float is approximately zero.",
        "The reported critical path is one longest path. Other zero-float tasks are listed separately.",
    ]
    if errors:
        return ScheduleResult(False, errors, warnings, [], 0.0, [], [], assumptions)

    cycle = _find_cycle(by_id)
    if cycle:
        rendered = " -> ".join(cycle)
        return ScheduleResult(
            False,
            [f"Dependency cycle detected: {rendered}."],
            warnings,
            [],
            0.0,
            [],
            [],
            assumptions,
        )

    order = _topo(by_id)
    if len(order) != len(by_id):
        return ScheduleResult(
            False,
            ["Dependency graph could not be ordered. A cycle may remain."],
            warnings,
            [],
            0.0,
            [],
            [],
            assumptions,
        )

    earliest_start: dict[str, float] = {}
    earliest_finish: dict[str, float] = {}
    for task_id in order:
        task = by_id[task_id]
        if not task.dependencies:
            start = 0.0
        else:
            start = 0.0
            for pred in task.dependencies:
                lag = task.lags.get(pred, 0.0)
                start = max(start, earliest_finish[pred] + lag)
        earliest_start[task_id] = start
        earliest_finish[task_id] = start + max(task.duration, 0.0)

    project_duration = max(earliest_finish.values(), default=0.0)
    successors: dict[str, list[str]] = {task_id: [] for task_id in by_id}
    for task in by_id.values():
        for pred in task.dependencies:
            successors[pred].append(task.id)

    latest_finish: dict[str, float] = {}
    latest_start: dict[str, float] = {}
    for task_id in reversed(order):
        task = by_id[task_id]
        if not successors[task_id]:
            finish = project_duration
        else:
            finish = project_duration
            for succ_id in successors[task_id]:
                lag = by_id[succ_id].lags.get(task_id, 0.0)
                finish = min(finish, latest_start[succ_id] - lag)
        latest_finish[task_id] = finish
        latest_start[task_id] = finish - max(task.duration, 0.0)

    scheduled: list[ScheduledTask] = []
    critical_ids: list[str] = []
    for task_id in order:
        task = by_id[task_id]
        total_float = latest_start[task_id] - earliest_start[task_id]
        is_critical = abs(total_float) <= _EPS
        if is_critical:
            critical_ids.append(task_id)
        start_date = None
        exclusive_finish = None
        inclusive = None
        if project_start is not None:
            start_date = add_days(project_start, earliest_start[task_id], calendar)
            exclusive_finish = add_days(project_start, earliest_finish[task_id], calendar)
            if task.duration <= _EPS:
                inclusive = start_date
            else:
                inclusive = inclusive_finish(project_start, earliest_finish[task_id], calendar)
        scheduled.append(
            ScheduledTask(
                id=task.id,
                name=task.name,
                duration=task.duration,
                earliest_start=earliest_start[task_id],
                earliest_finish=earliest_finish[task_id],
                latest_start=latest_start[task_id],
                latest_finish=latest_finish[task_id],
                total_float=total_float,
                is_critical=is_critical,
                milestone=task.milestone,
                phase=task.phase,
                wbs_code=task.wbs_code,
                start_date=start_date,
                finish_date=inclusive,
                exclusive_finish_date=exclusive_finish,
                dependencies=list(task.dependencies),
            )
        )

    critical_path = _longest_path(order, by_id, earliest_finish, critical_ids)
    return ScheduleResult(
        True,
        [],
        warnings,
        scheduled,
        project_duration,
        critical_path,
        critical_ids,
        assumptions,
    )


def _longest_path(
    order: list[str],
    by_id: dict[str, SchedTask],
    earliest_finish: dict[str, float],
    critical_ids: list[str],
) -> list[str]:
    if not critical_ids:
        return []
    critical = set(critical_ids)
    # Reconstruct a single path by walking critical predecessors with the
    # greatest exclusive finish. Ties break on task id for reproducibility.
    ends = [
        task_id
        for task_id in critical
        if not any(
            succ in critical and task_id in by_id[succ].dependencies for succ in by_id
        )
    ]
    if not ends:
        ends = list(critical)
    current = sorted(ends, key=lambda task_id: (-earliest_finish[task_id], task_id))[0]
    path = [current]
    guard = 0
    while guard <= len(by_id):
        guard += 1
        preds = [pred for pred in by_id[current].dependencies if pred in critical]
        if not preds:
            break
        current = sorted(preds, key=lambda task_id: (-earliest_finish[task_id], task_id))[0]
        path.append(current)
    path.reverse()
    return path
