"""Residential tower demonstration.

The quantities below are the example brief. Costs and durations come from the
sample model, not from a measured estimate.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.planning import (
    create_project,
    create_scenario,
    execute_simulation,
    patch_from_payload,
)

DEMO_PROMPT = (
    "Plan a 20-story residential building with three basement parking levels, "
    "25,000 square meters of gross floor area, a $15 million budget, and a "
    "30-month construction schedule. Generate a 3D conceptual model, construction "
    "phases, project schedule, cost breakdown, resource plan, risk register, and "
    "alternative scenarios."
)

DEMO_STRUCTURED = {
    "name": "Residential Tower Demonstration",
    "category": "construction",
    "start_date": "2026-01-05",
    "floors": 20,
    "basements": 3,
    "gfa_sqm": 25000,
    "budget_amount": 15000000,
    "currency": "USD",
    "duration_months": 30,
}

WORKFORCE = {
    "name": "Increased structure workforce",
    "description": (
        "Twenty percent more crews are available for scalable superstructure and interior work. "
        "The configured productivity gain is 12 percent, not a matching 20 percent cut. "
        "Tasks that are not marked scalable keep their durations. Concurrency limits are unchanged."
    ),
    "duration_factors": {"superstructure": round(1 / 1.12, 4), "interiors": round(1 / 1.12, 4)},
    "scalable_only": True,
    "scalable_phases": ["superstructure", "interiors"],
    "notes": [
        "Input crew scale: 1.20.",
        "Productivity factor applied to scalable tasks only: 1.12.",
        "Non-scalable tasks are unchanged.",
    ],
}

MATERIALS = {
    "name": "Higher material prices",
    "description": (
        "Material allowances are increased 15 percent from the sample rate card. "
        "Labor, equipment, and service rates stay the same. Overhead and contingency "
        "percentages are reapplied to the new direct total."
    ),
    "cost_category_factors": {"materials": 1.15},
}

FACADE = {
    "name": "Accelerated facade overlap",
    "description": (
        "The facade starts 120 days before the superstructure finishes, using a negative "
        "finish-to-start lag. The tower crane is shared, so the overlap can overload it. "
        "This does not add workers and does not shorten every task."
    ),
    "lag_overrides": [["CON-ENV", "CON-SUPER", -120]],
}


def seed_residential_demo(db: Session, owner_id: str):
    project = create_project(db, owner_id, DEMO_PROMPT, DEMO_STRUCTURED, generate=True)
    execute_simulation(
        db,
        project,
        run_type="monte_carlo",
        seed=42,
        iterations=200,
        scenario=None,
        set_baseline=False,
    )
    for raw in (WORKFORCE, MATERIALS, FACADE):
        scenario, _notes = create_scenario(db, project, patch_from_payload(raw), raw)
        execute_simulation(
            db,
            project,
            run_type="deterministic",
            seed=None,
            iterations=None,
            scenario=scenario,
            set_baseline=False,
        )
        execute_simulation(
            db,
            project,
            run_type="monte_carlo",
            seed=42,
            iterations=80,
            scenario=scenario,
            set_baseline=False,
        )
    db.commit()
    db.refresh(project)
    return project
