"""Deterministic project simulation engine.

Scheduling, cost aggregation, resource analysis, and Monte Carlo statistics
are computed here. Optional language-model adapters may help interpret text,
but they do not own these calculations.
"""

from app.engine.budget import aggregate_costs
from app.engine.monte_carlo import run_monte_carlo
from app.engine.resources import analyze_resources
from app.engine.scheduler import schedule_tasks

ENGINE_VERSION = "1.0.0"

__all__ = [
    "ENGINE_VERSION",
    "aggregate_costs",
    "analyze_resources",
    "run_monte_carlo",
    "schedule_tasks",
]
