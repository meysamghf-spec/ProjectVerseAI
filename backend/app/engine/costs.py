"""Transparent sample cost models.

Rates live in SAMPLE_RATES and are labeled as planning assumptions dated
2026-01-01. They are not live market prices and must not be presented as bids.
"""

from __future__ import annotations

from app.engine.types import CostLine

SAMPLE_RATE_DATE = "2026-01-01"
SAMPLE_RATE_SOURCE = "projectverse-sample-assumptions"

SAMPLE_RATES = {
    "source": SAMPLE_RATE_SOURCE,
    "as_of": SAMPLE_RATE_DATE,
    "disclaimer": "Sample planning assumptions. Not market prices, quotations, or location-adjusted estimates.",
    "labor_per_sqm": 180.0,
    "materials_per_sqm": 160.0,
    "equipment_per_sqm": 55.0,
    "services_per_sqm": 40.0,
    "overhead_pct": 0.12,
    "contingency_pct": 0.08,
    "basement_each": 250_000.0,
    "high_rise_threshold_floors": 12,
    "high_rise_premium_per_floor": 40_000.0,
    "default_daily_labor_rate": 650.0,
    "currency": "USD",
}


def _line(
    line_id: str,
    name: str,
    category: str,
    amount: float,
    *,
    phase: str | None = None,
    task_id: str | None = None,
    notes: str,
    include: bool = True,
    quantity: float = 1.0,
    unit: str = "lump_sum",
    spread: float = 0.15,
) -> CostLine:
    return CostLine(
        id=line_id,
        name=name,
        category=category,
        amount=round(amount, 2),
        task_id=task_id,
        phase=phase,
        include_in_total=include,
        source=SAMPLE_RATE_SOURCE,
        source_date=SAMPLE_RATE_DATE,
        notes=notes,
        amount_min=round(amount * (1 - spread), 2),
        amount_mode=round(amount, 2),
        amount_max=round(amount * (1 + spread), 2),
        quantity=quantity,
        unit=unit,
        unit_cost=round(amount / quantity, 4) if quantity else round(amount, 2),
    )


PHASE_WEIGHTS = (
    ("preconstruction", 0.08),
    ("substructure", 0.18),
    ("superstructure", 0.34),
    ("envelope", 0.12),
    ("mep", 0.10),
    ("interiors", 0.12),
    ("closeout", 0.06),
)


def _allocate(amount: float, weights: tuple[tuple[str, float], ...]) -> list[tuple[str, float]]:
    """Split an amount by weight. The last slice absorbs rounding residue."""

    raw = [round(amount * weight, 2) for _, weight in weights]
    raw[-1] = round(amount - sum(raw[:-1]), 2)
    return [(phase, value) for (phase, _), value in zip(weights, raw)]


def construction_cost_lines(
    gfa: float,
    floors: int,
    basements: int,
    rates: dict | None = None,
) -> tuple[list[CostLine], dict]:
    rates = {**SAMPLE_RATES, **(rates or {})}
    note = (
        f"Sample rate from {rates['source']} dated {rates['as_of']}. "
        "Not a vendor quote. Phase shares are planning weights, not measured bids."
    )
    labor = gfa * float(rates["labor_per_sqm"])
    materials = gfa * float(rates["materials_per_sqm"])
    equipment = gfa * float(rates["equipment_per_sqm"])
    services = gfa * float(rates["services_per_sqm"])
    extra_floors = max(0, int(floors) - int(rates["high_rise_threshold_floors"]))
    high_rise = extra_floors * float(rates["high_rise_premium_per_floor"])
    basement = int(basements) * float(rates["basement_each"])
    # Overhead applies to every direct allowance, including height and basement allowances.
    # Contingency applies after overhead. Monte Carlo uses the same two percentages.
    direct = labor + materials + equipment + services + high_rise + basement
    overhead = direct * float(rates["overhead_pct"])
    contingency = (direct + overhead) * float(rates["contingency_pct"])
    lines: list[CostLine] = []
    direct_ids: list[str] = []
    for category, total, unit in (
        ("labor", labor, "sqm"),
        ("materials", materials, "sqm"),
        ("equipment", equipment, "sqm"),
        ("services", services, "sqm"),
    ):
        for phase, share in _allocate(total, PHASE_WEIGHTS):
            line_id = f"{category}-{phase}"
            direct_ids.append(line_id)
            lines.append(
                _line(
                    line_id,
                    f"{category.title()} allowance ({phase})",
                    category,
                    share,
                    phase=phase,
                    notes=note,
                    quantity=gfa,
                    unit=unit,
                )
            )
    direct_ids.extend(["high-rise", "basement"])
    lines.extend(
        [
            _line(
                "high-rise",
                "High-rise complexity allowance",
                "other",
                high_rise,
                phase="superstructure",
                notes="Applied only above the configured floor threshold. Sample allowance, not a structural premium study.",
            ),
            _line(
                "basement",
                "Basement allowance",
                "other",
                basement,
                phase="substructure",
                notes="Flat sample allowance per basement level.",
            ),
            _line(
                "overhead",
                "Overhead",
                "overhead",
                overhead,
                notes="Overhead percentage applied to all direct allowances. Excluded from direct Monte Carlo sampling and reapplied afterwards.",
                spread=0.0,
            ),
            _line(
                "contingency",
                "Contingency",
                "contingency",
                contingency,
                notes="Contingency percentage applied after overhead and allowances. Recomputed in each Monte Carlo iteration.",
                spread=0.0,
            ),
        ]
    )
    model = {
        "overhead_pct": float(rates["overhead_pct"]),
        "contingency_pct": float(rates["contingency_pct"]),
        "direct_line_ids": direct_ids,
        "rates": rates,
    }
    return lines, model


def effort_cost_lines(
    tasks: list[dict],
    daily_rate: float,
    services_lump: float,
    overhead_pct: float,
    contingency_pct: float,
) -> tuple[list[CostLine], dict]:
    """Cost = duration x assigned people x daily rate, plus explicit lumps.

    Resource rates are not added a second time.
    """

    lines: list[CostLine] = []
    direct_ids: list[str] = []
    for task in tasks:
        people = float(task.get("people") or 0)
        days = float(task["duration"])
        amount = days * people * daily_rate
        line_id = f"labor-{task['id']}"
        direct_ids.append(line_id)
        lines.append(
            _line(
                line_id,
                f"Labor for {task['name']}",
                "labor",
                amount,
                phase=task.get("phase"),
                task_id=task["id"],
                notes=(
                    f"{days:g} days x {people:g} people x {daily_rate:g} sample daily rate. "
                    f"Source {SAMPLE_RATE_SOURCE} dated {SAMPLE_RATE_DATE}."
                ),
                quantity=days * people,
                unit="person_day",
            )
        )
    if services_lump:
        direct_ids.append("services")
        lines.append(
            _line(
                "services",
                "Tools and services allowance",
                "services",
                services_lump,
                notes="Fixed sample allowance. Not an invoice.",
            )
        )
    direct_total = sum(line.amount for line in lines)
    overhead = direct_total * overhead_pct
    subtotal = direct_total + overhead
    contingency = subtotal * contingency_pct
    lines.append(
        _line("overhead", "Overhead", "overhead", overhead, notes="Percentage of direct cost.", spread=0.0)
    )
    lines.append(
        _line(
            "contingency",
            "Contingency",
            "contingency",
            contingency,
            notes="Percentage applied after overhead.",
            spread=0.0,
        )
    )
    model = {
        "overhead_pct": overhead_pct,
        "contingency_pct": contingency_pct,
        "direct_line_ids": direct_ids,
        "daily_rate": daily_rate,
        "rates": {
            "source": SAMPLE_RATE_SOURCE,
            "as_of": SAMPLE_RATE_DATE,
            "default_daily_labor_rate": daily_rate,
        },
    }
    return lines, model
