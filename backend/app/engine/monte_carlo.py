"""Seeded, dependency-aware Monte Carlo simulation.

Every iteration draws task durations and direct costs, recomputes the critical
path, then rebuilds overhead and contingency from the configured percentages.
Percentiles and probabilities are summaries of those iterations.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.engine.distributions import pearson, percentile, sample_triangular, validate_triangular
from app.engine.scheduler import schedule_tasks
from app.engine.types import CostLine, SchedTask, WorkCalendar

MIN_ITERATIONS = 2
MAX_ITERATIONS = 10000
WARN_ITERATIONS = 100


@dataclass
class MonteCarloResult:
    seed: int
    iterations: int
    duration_samples: list[float]
    cost_samples: list[float]
    p50_duration: float
    p80_duration: float
    p90_duration: float
    p50_cost: float
    p80_cost: float
    p90_cost: float
    deadline_probability: float | None
    budget_probability: float | None
    schedule_contributors: list[dict]
    cost_contributors: list[dict]
    warnings: list[str]
    assumptions: list[str]
    deterministic_duration: float
    deterministic_cost: float


@dataclass
class CostModel:
    overhead_pct: float = 0.0
    contingency_pct: float = 0.0
    direct_lines: list[CostLine] = field(default_factory=list)


def _bounds(mode: float, low: float | None, high: float | None, spread: float) -> tuple[float, float, float]:
    resolved_low = mode if low is None else low
    resolved_high = mode if high is None else high
    if low is None and high is None and spread > 0:
        resolved_low = mode * (1 - spread)
        resolved_high = mode * (1 + spread)
    return resolved_low, mode, resolved_high


def run_monte_carlo(
    tasks: list[SchedTask],
    *,
    seed: int,
    iterations: int,
    calendar: WorkCalendar | None = None,
    cost_model: CostModel | None = None,
    deadline_day: float | None = None,
    budget: float | None = None,
    duration_spread: float = 0.0,
    cost_spread: float = 0.0,
) -> MonteCarloResult:
    if iterations < MIN_ITERATIONS or iterations > MAX_ITERATIONS:
        raise ValueError(
            f"Iteration count must be between {MIN_ITERATIONS} and {MAX_ITERATIONS}."
        )
    if not tasks:
        raise ValueError("Monte Carlo requires at least one task.")

    warnings: list[str] = []
    if iterations < WARN_ITERATIONS:
        warnings.append(
            f"Only {iterations} iterations were run. Percentiles are reproducible but coarse."
        )

    calendar = calendar or WorkCalendar()
    cost_model = cost_model or CostModel()
    deterministic = schedule_tasks(tasks, calendar=calendar)
    if not deterministic.ok:
        raise ValueError("Deterministic schedule failed: " + "; ".join(deterministic.errors))

    direct_lines = list(cost_model.direct_lines)
    for line in direct_lines:
        low, mode, high = _bounds(line.amount, line.amount_min, line.amount_max, cost_spread)
        validate_triangular(low, mode, high, f"Cost line '{line.id}'")
        if low < -1e-9:
            raise ValueError(f"Cost line '{line.id}' has a negative minimum.")

    for task in tasks:
        low, mode, high = _bounds(task.duration, task.duration_min, task.duration_max, duration_spread)
        validate_triangular(low, mode, high, f"Task '{task.id}' duration")
        if low < -1e-9:
            raise ValueError(f"Task '{task.id}' duration minimum is negative.")

    deterministic_direct = sum(line.amount for line in direct_lines)
    deterministic_overhead = deterministic_direct * cost_model.overhead_pct
    deterministic_subtotal = deterministic_direct + deterministic_overhead
    deterministic_cost = deterministic_subtotal * (1 + cost_model.contingency_pct)

    rng = random.Random(seed)
    duration_samples: list[float] = []
    cost_samples: list[float] = []
    per_task: dict[str, list[float]] = {task.id: [] for task in tasks}
    per_line: dict[str, list[float]] = {line.id: [] for line in direct_lines}

    for _ in range(iterations):
        sampled_tasks: list[SchedTask] = []
        for task in tasks:
            if task.milestone:
                drawn = 0.0
            else:
                low, mode, high = _bounds(
                    task.duration, task.duration_min, task.duration_max, duration_spread
                )
                drawn = sample_triangular(rng, low, mode, high)
            per_task[task.id].append(drawn)
            sampled_tasks.append(
                SchedTask(
                    id=task.id,
                    name=task.name,
                    duration=drawn,
                    dependencies=list(task.dependencies),
                    lags=dict(task.lags),
                    milestone=task.milestone,
                    phase=task.phase,
                )
            )
        outcome = schedule_tasks(sampled_tasks, calendar=calendar)
        if not outcome.ok:
            raise ValueError("Sampled schedule failed: " + "; ".join(outcome.errors))
        duration_samples.append(outcome.project_duration)

        direct = 0.0
        for line in direct_lines:
            low, mode, high = _bounds(line.amount, line.amount_min, line.amount_max, cost_spread)
            drawn_cost = sample_triangular(rng, max(low, 0.0), max(mode, 0.0), max(high, 0.0))
            per_line[line.id].append(drawn_cost)
            direct += drawn_cost
        overhead = direct * cost_model.overhead_pct
        total = (direct + overhead) * (1 + cost_model.contingency_pct)
        cost_samples.append(total)

    schedule_contributors = _contributors(per_task, duration_samples, tasks)
    cost_contributors = _line_contributors(per_line, cost_samples, direct_lines)

    deadline_probability = None
    if deadline_day is not None:
        hits = sum(1 for sample in duration_samples if sample <= deadline_day + 1e-9)
        deadline_probability = hits / iterations
    budget_probability = None
    if budget is not None:
        hits = sum(1 for sample in cost_samples if sample <= budget + 1e-6)
        budget_probability = hits / iterations

    assumptions = [
        "Each iteration samples triangular durations and direct costs, then reschedules the full dependency graph.",
        "Overhead and contingency are reapplied to each iteration's sampled direct cost. They are not sampled as extra independent line items.",
        "The random generator is Python's random.Random seeded with the recorded seed.",
        "P50, P80, and P90 use linear interpolation on the sorted samples from this run.",
        "A deadline or budget probability is omitted, not guessed, when no target was supplied.",
        "These results are model outputs, not confidence intervals from field measurements.",
    ]
    return MonteCarloResult(
        seed=seed,
        iterations=iterations,
        duration_samples=duration_samples,
        cost_samples=cost_samples,
        p50_duration=percentile(duration_samples, 50),
        p80_duration=percentile(duration_samples, 80),
        p90_duration=percentile(duration_samples, 90),
        p50_cost=percentile(cost_samples, 50),
        p80_cost=percentile(cost_samples, 80),
        p90_cost=percentile(cost_samples, 90),
        deadline_probability=deadline_probability,
        budget_probability=budget_probability,
        schedule_contributors=schedule_contributors,
        cost_contributors=cost_contributors,
        warnings=warnings,
        assumptions=assumptions,
        deterministic_duration=deterministic.project_duration,
        deterministic_cost=deterministic_cost,
    )


def _contributors(per_task: dict[str, list[float]], project: list[float], tasks: list[SchedTask]) -> list[dict]:
    names = {task.id: task.name for task in tasks}
    rows = []
    for task_id, samples in per_task.items():
        coefficient = pearson(samples, project)
        rows.append(
            {
                "id": task_id,
                "name": names.get(task_id, task_id),
                "correlation": coefficient,
                "mean": sum(samples) / len(samples),
            }
        )
    rows.sort(key=lambda row: (-abs(row["correlation"]), row["id"]))
    return rows


def _line_contributors(per_line: dict[str, list[float]], totals: list[float], lines: list[CostLine]) -> list[dict]:
    names = {line.id: line.name for line in lines}
    rows = []
    for line_id, samples in per_line.items():
        coefficient = pearson(samples, totals)
        rows.append(
            {
                "id": line_id,
                "name": names.get(line_id, line_id),
                "correlation": coefficient,
                "mean": sum(samples) / len(samples),
            }
        )
    rows.sort(key=lambda row: (-abs(row["correlation"]), row["id"]))
    return rows
