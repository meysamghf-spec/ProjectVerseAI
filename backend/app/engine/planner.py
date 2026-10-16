"""Project-type templates.

Templates produce editable tasks, dependencies, resources, costs, and risks.
Duration coefficients for the residential demonstration are documented sample
assumptions. They are calibrated so the sample 20-story, 3-basement tower has
a 900-day critical path (30 planning months of 30 days). They are not industry
productivity standards.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.engine.costs import SAMPLE_RATES, construction_cost_lines, effort_cost_lines
from app.engine.scene import construction_scene, generic_scene
from app.engine.types import CostLine, ResourceDemand, ResourcePool, SchedTask

DEMO_SUPERSTRUCTURE_DAYS_PER_FLOOR = 15
DEMO_BASEMENT_DAYS = 30


@dataclass
class PlanDraft:
    summary: str
    tasks: list[SchedTask]
    wbs: list[dict]
    resources: list[ResourcePool]
    costs: list[CostLine]
    cost_model: dict
    risks: list[dict]
    milestones: list[dict]
    assumptions: list[dict]
    deliverables: list[str]
    scene: dict
    warnings: list[str] = field(default_factory=list)


def _task(
    code: str,
    name: str,
    duration: float,
    deps: list[str],
    phase: str,
    description: str,
    *,
    milestone: bool = False,
    scalable: bool = False,
    resources: list[tuple[str, float]] | None = None,
    parent: str | None = None,
    spread: float = 0.15,
) -> SchedTask:
    return SchedTask(
        id=code,
        name=name,
        duration=duration,
        dependencies=list(deps),
        milestone=milestone,
        scalable=scalable,
        phase=phase,
        wbs_code=code,
        description=description,
        parent_code=parent,
        duration_min=0.0 if milestone else round(duration * (1 - spread), 2),
        duration_mode=duration,
        duration_max=0.0 if milestone else round(duration * (1 + spread), 2),
        resources=[ResourceDemand(resource_id, qty) for resource_id, qty in (resources or [])],
    )


def _wbs(code: str, name: str, parent: str | None = None) -> dict:
    return {"code": code, "name": name, "parent_code": parent, "summary": True}


def generate_plan(values: dict, extraction_assumptions: list[dict] | None = None) -> PlanDraft:
    project_type = str(values.get("project_type") or "custom")
    builders = {
        "construction": _construction,
        "software": _software,
        "manufacturing": _manufacturing,
        "infrastructure": _infrastructure,
        "urban": _urban,
        "logistics": _logistics,
        "research": _research,
        "event": _event,
    }
    builder = builders.get(project_type, _custom)
    draft = builder(values)
    _apply_currency(draft, values)
    for item in extraction_assumptions or []:
        draft.assumptions.append(item)
    draft.assumptions.append(
        {
            "key": "estimate_status",
            "value": "unverified_sample_model",
            "rationale": "All generated durations and costs are model assumptions until a user replaces them.",
            "source": "assumption",
            "confidence": 0.2,
        }
    )
    return draft


_LOCAL_RATE_KEYS = ("labor_per_sqm", "materials_per_sqm", "equipment_per_sqm", "services_per_sqm")


def _apply_currency(draft: PlanDraft, values: dict) -> None:
    """Sample rates are USD. Convert them for other currencies only with a user-supplied rate."""

    currency = str(values.get("currency") or "USD").upper()
    if currency == "USD":
        return
    fx = values.get("usd_exchange_rate")
    own_rates = any(values.get(key) is not None for key in _LOCAL_RATE_KEYS)
    if own_rates:
        draft.warnings.append(
            f"Unit rates you entered are used as {currency}. Bundled sample allowances that you did not "
            "replace are still USD figures."
        )
        return
    if not fx:
        draft.warnings.append(
            f"Costs use the bundled USD sample rates and are NOT converted to {currency}. "
            f"Set usd_exchange_rate ({currency} per 1 USD) or enter local unit rates before reading totals."
        )
        draft.assumptions.append(
            {
                "key": "cost_currency_basis",
                "value": "USD sample rates, unconverted",
                "rationale": f"No usd_exchange_rate was given for {currency}.",
                "source": "assumption",
                "confidence": 0.1,
            }
        )
        return
    factor = float(fx)
    for line in draft.costs:
        line.amount = round(line.amount * factor, 2)
        line.unit_cost = round(line.unit_cost * factor, 2)
        for attr in ("amount_min", "amount_mode", "amount_max"):
            value = getattr(line, attr)
            if value is not None:
                setattr(line, attr, round(value * factor, 2))
    for risk in draft.risks:
        if risk.get("impact_cost"):
            risk["impact_cost"] = round(float(risk["impact_cost"]) * factor, 2)
    draft.assumptions.append(
        {
            "key": "usd_exchange_rate",
            "value": factor,
            "rationale": f"USD sample rates converted at {factor:g} {currency} per USD (user-supplied).",
            "source": "user",
            "confidence": 0.6,
        }
    )


def _construction(values: dict) -> PlanDraft:
    floors = int(values.get("floors") or 4)
    basements = int(values.get("basements") or 0)
    gfa = float(values.get("gfa_sqm") or floors * 800)
    rates = dict(SAMPLE_RATES)
    for key in (
        "labor_per_sqm",
        "materials_per_sqm",
        "equipment_per_sqm",
        "services_per_sqm",
        "overhead_pct",
        "contingency_pct",
    ):
        if values.get(key) is not None:
            rates[key] = values[key]

    basement_duration = DEMO_BASEMENT_DAYS * basements
    super_duration = DEMO_SUPERSTRUCTURE_DAYS_PER_FLOOR * max(floors, 1)
    tasks = [
        _task("CON-PERMIT", "Permitting and design coordination", 40, [], "preconstruction",
              "Assumed to overlap mobilization. Many real projects must finish permits first.", parent="1.0"),
        _task("CON-MOB", "Mobilization", 36, [], "preconstruction",
              "Site setup. Duration is a fixed sample allowance.", parent="1.0", resources=[("superintendent", 1)]),
        _task("CON-PROCURE", "Long-lead procurement", 180, ["CON-PERMIT"], "preconstruction",
              "Procurement must finish before superstructure. It is not automatically critical.", parent="1.0"),
        _task("CON-EXC", "Excavation", 72, ["CON-MOB"], "substructure",
              "Bulk excavation allowance.", parent="2.0", resources=[("excavation-crew", 1)]),
        _task("CON-FOUND", "Foundations", 66, ["CON-EXC"], "substructure",
              "Foundations allowance after excavation.", parent="2.0", resources=[("structure-crew", 2)]),
    ]
    super_deps = ["CON-FOUND", "CON-PROCURE"]
    if basement_duration > 0:
        tasks.append(
            _task(
                "CON-BASE",
                "Basement structure",
                basement_duration,
                ["CON-FOUND"],
                "substructure",
                f"{basements} basement level(s) at {DEMO_BASEMENT_DAYS} sample days each.",
                parent="2.0",
                resources=[("structure-crew", 2), ("tower-crane", 1)],
            )
        )
        super_deps = ["CON-BASE", "CON-PROCURE"]
    tasks.extend(
        [
            _task(
                "CON-SUPER",
                "Superstructure",
                super_duration,
                super_deps,
                "superstructure",
                f"{floors} floors at {DEMO_SUPERSTRUCTURE_DAYS_PER_FLOOR} sample days each. Crew scaling can change this task only.",
                scalable=True,
                parent="3.0",
                resources=[("structure-crew", 2), ("tower-crane", 1)],
            ),
            _task("CON-ENV", "Envelope and facade", 120, ["CON-SUPER"], "envelope",
                  "Starts after superstructure in the baseline, so the tower crane is not double-booked.",
                  parent="4.0", resources=[("facade-crew", 1), ("tower-crane", 1)]),
            _task("CON-MEP", "MEP rough-in", 100, ["CON-SUPER"], "mep",
                  "Runs in parallel with the envelope.", parent="5.0", resources=[("mep-crew", 2)]),
            _task(
                "CON-INT",
                "Interior fit-out",
                156,
                ["CON-ENV", "CON-MEP"],
                "interiors",
                "Starts after both envelope and MEP. Marked scalable for workforce scenarios.",
                scalable=True,
                parent="5.0",
                resources=[("interior-crew", 2)],
            ),
            _task("CON-COMM", "Commissioning", 60, ["CON-INT"], "closeout",
                  "Systems commissioning allowance.", parent="6.0", resources=[("commissioning-team", 1)]),
            _task("CON-HAND", "Handover", 0, ["CON-COMM"], "closeout",
                  "Milestone. Zero duration.", milestone=True, parent="6.0"),
        ]
    )
    wbs = [
        _wbs("1.0", "Preconstruction"),
        _wbs("2.0", "Substructure"),
        _wbs("3.0", "Superstructure"),
        _wbs("4.0", "Envelope"),
        _wbs("5.0", "Interiors and MEP"),
        _wbs("6.0", "Closeout"),
    ]
    resources = [
        ResourcePool("superintendent", "Superintendent", 1, "labor", "person", 900),
        ResourcePool("excavation-crew", "Excavation crew", 1, "labor", "crew", 2200),
        ResourcePool("structure-crew", "Structure crew", 2, "labor", "crew", 2800),
        ResourcePool("facade-crew", "Facade crew", 1, "labor", "crew", 2400),
        ResourcePool("mep-crew", "MEP crew", 2, "labor", "crew", 2100),
        ResourcePool("interior-crew", "Interior crew", 2, "labor", "crew", 1800),
        ResourcePool("tower-crane", "Tower crane", 1, "equipment", "crane", 1500),
        ResourcePool("commissioning-team", "Commissioning team", 1, "labor", "team", 1600),
    ]
    costs, model = construction_cost_lines(gfa, floors, basements, rates)
    risks = [
        {
            "code": "R1",
            "title": "Permit duration may not overlap mobilization",
            "description": "The template starts mobilization in parallel with permitting.",
            "category": "schedule",
            "probability": 0.4,
            "impact_cost": 0,
            "impact_schedule_days": 40,
            "mitigation": "Confirm the approval path before treating mobilization as independent.",
            "status": "open",
        },
        {
            "code": "R2",
            "title": "Sample unit rates are not local prices",
            "description": "Cost lines use the bundled sample rate card dated 2026-01-01.",
            "category": "cost",
            "probability": 0.7,
            "impact_cost": round(sum(line.amount for line in costs if line.include_in_total) * 0.15, 2),
            "impact_schedule_days": 0,
            "mitigation": "Replace sample rates with user-provided or imported prices and record the source date.",
            "status": "open",
        },
        {
            "code": "R3",
            "title": "Single tower crane constrains structure and facade",
            "description": "Baseline logic sequences facade after superstructure so the crane is not overloaded.",
            "category": "resource",
            "probability": 0.5,
            "impact_cost": 150000,
            "impact_schedule_days": 20,
            "mitigation": "If facade is overlapped with structure, add crane capacity or accept the overload warning.",
            "status": "open",
        },
        {
            "code": "R4",
            "title": "Subsurface conditions are unknown",
            "description": "No geotechnical facts were supplied.",
            "category": "scope",
            "probability": 0.45,
            "impact_cost": 400000,
            "impact_schedule_days": 30,
            "mitigation": "Treat foundation duration and cost as assumptions until a site investigation exists.",
            "status": "open",
        },
    ]
    for risk in risks:
        risk["score"] = round(risk["probability"] * (risk["impact_schedule_days"] + risk["impact_cost"] / 100000), 2)
    assumptions = [
        {
            "key": "duration_coefficients",
            "value": {
                "mobilization_days": 36,
                "excavation_days": 72,
                "foundation_days": 66,
                "days_per_basement": DEMO_BASEMENT_DAYS,
                "days_per_floor": DEMO_SUPERSTRUCTURE_DAYS_PER_FLOOR,
                "envelope_days": 120,
                "mep_days": 100,
                "interior_days": 156,
                "commissioning_days": 60,
                "month_days": 30,
            },
            "rationale": (
                "These coefficients make the 20-floor, 3-basement demonstration land on a 900-day "
                "critical path. Changing floors or basements changes the calculated duration."
            ),
            "source": "assumption",
            "confidence": 0.25,
        },
        {
            "key": "permit_overlap",
            "value": True,
            "rationale": "Permitting is parallel with mobilization in this template.",
            "source": "assumption",
            "confidence": 0.3,
        },
        {
            "key": "sample_rates",
            "value": rates,
            "rationale": SAMPLE_RATES["disclaimer"],
            "source": "assumption",
            "confidence": 0.2,
        },
    ]
    scene_assumptions = {
        "floor_to_floor_height_m": values.get("floor_to_floor_height_m") or 3.2,
        "basement_height_m": values.get("basement_height_m") or 3.0,
        "aspect_ratio": values.get("aspect_ratio") or 1.5,
    }
    return PlanDraft(
        summary=(
            f"Conceptual plan for a {floors}-story building"
            f"{f' with {basements} basement level(s)' if basements else ''}"
            f" and about {gfa:,.0f} square meters of gross floor area. "
            "Durations and costs are sample planning assumptions."
        ),
        tasks=tasks,
        wbs=wbs,
        resources=resources,
        costs=costs,
        cost_model=model,
        risks=risks,
        milestones=[
            {"code": "CON-HAND", "name": "Handover", "task_code": "CON-HAND"},
            {"code": "M-STRUCTURE", "name": "Structure complete", "task_code": "CON-SUPER"},
        ],
        assumptions=assumptions,
        deliverables=[
            "Work breakdown structure",
            "Dependency-based schedule",
            "Sample cost breakdown",
            "Resource loading",
            "Risk register",
            "Conceptual 3D massing",
        ],
        scene=construction_scene(gfa, floors, basements, scene_assumptions),
        warnings=[
            "Construction output is a conceptual planning model, not a construction estimate or structural design."
        ],
    )


def _effort_plan(
    project_type: str,
    summary: str,
    wbs: list[dict],
    tasks: list[SchedTask],
    resources: list[ResourcePool],
    risks: list[dict],
    deliverables: list[str],
    phases: list[str],
    people_by_task: dict[str, float],
    daily_rate: float = 650.0,
    services_lump: float = 8000.0,
) -> PlanDraft:
    task_rows = [
        {
            "id": task.id,
            "name": task.name,
            "duration": task.duration,
            "phase": task.phase,
            "people": people_by_task.get(task.id, 0),
        }
        for task in tasks
        if not task.milestone
    ]
    costs, model = effort_cost_lines(task_rows, daily_rate, services_lump, 0.10, 0.10)
    for risk in risks:
        risk["score"] = round(
            float(risk["probability"]) * (float(risk["impact_schedule_days"]) + float(risk["impact_cost"]) / 100000),
            2,
        )
    return PlanDraft(
        summary=summary,
        tasks=tasks,
        wbs=wbs,
        resources=resources,
        costs=costs,
        cost_model=model,
        risks=risks,
        milestones=[{"code": task.id, "name": task.name, "task_code": task.id} for task in tasks if task.milestone],
        assumptions=[
            {
                "key": "daily_labor_rate",
                "value": daily_rate,
                "rationale": f"Sample loaded daily rate from {SAMPLE_RATES['source']} dated {SAMPLE_RATES['as_of']}.",
                "source": "assumption",
                "confidence": 0.2,
            },
            {
                "key": "crew_assignments",
                "value": people_by_task,
                "rationale": "Headcount used only for the effort cost model. It does not silently compress durations.",
                "source": "assumption",
                "confidence": 0.3,
            },
        ],
        deliverables=deliverables,
        scene=generic_scene(project_type, phases),
        warnings=[
            "This plan is a template scaled by the stated inputs. It is not a verified delivery commitment."
        ],
    )


def _software(values: dict) -> PlanDraft:
    team = int(values.get("team_size") or 6)
    tasks = [
        _task("SW-DISC", "Discovery", 10, [], "discovery", "Scope and constraints workshop.", parent="1.0"),
        _task("SW-ARCH", "Architecture", 12, ["SW-DISC"], "architecture", "Module and interface outline.", parent="1.0"),
        _task("SW-BACK", "Backend services", 30, ["SW-ARCH"], "build", "Service implementation.", scalable=True, parent="2.0",
              resources=[("engineers", min(team, 4))]),
        _task("SW-FRONT", "Client application", 28, ["SW-ARCH"], "build", "Client implementation in parallel with backend.",
              scalable=True, parent="2.0", resources=[("engineers", min(team, 3))]),
        _task("SW-INT", "Integration", 10, ["SW-BACK", "SW-FRONT"], "integration", "Join the parallel workstreams.", parent="3.0"),
        _task("SW-TEST", "Testing and fix", 12, ["SW-INT"], "verification", "Verification window.", parent="3.0"),
        _task("SW-REL", "Release", 0, ["SW-TEST"], "release", "Release milestone.", milestone=True, parent="4.0"),
    ]
    people = {"SW-DISC": 3, "SW-ARCH": 3, "SW-BACK": min(team, 4), "SW-FRONT": min(max(team - 2, 2), 4), "SW-INT": 4, "SW-TEST": 3}
    return _effort_plan(
        "software",
        f"Software delivery template using an assumed team of {team}. Parallel backend and client work join at integration.",
        [_wbs("1.0", "Definition"), _wbs("2.0", "Build"), _wbs("3.0", "Integration"), _wbs("4.0", "Release")],
        tasks,
        [ResourcePool("engineers", "Engineers", float(team), "labor", "person", 650)],
        [
            {
                "code": "R1",
                "title": "Integration waits on both workstreams",
                "description": "The later of backend and client sets the integration start.",
                "category": "schedule",
                "probability": 0.5,
                "impact_cost": 20000,
                "impact_schedule_days": 10,
                "mitigation": "Keep interfaces stable so neither stream silently extends.",
                "status": "open",
            }
        ],
        ["Module plan", "Milestone schedule", "Effort-based cost", "Conceptual system diagram"],
        ["discovery", "architecture", "build", "integration", "verification", "release"],
        people,
    )


def _manufacturing(values: dict) -> PlanDraft:
    tasks = [
        _task("MF-LAY", "Line layout", 15, [], "layout", "Station arrangement.", parent="1.0"),
        _task("MF-RECV", "Receiving setup", 20, ["MF-LAY"], "receiving", "Inbound station.", parent="2.0"),
        _task("MF-FAB", "Fabrication station", 30, ["MF-LAY"], "fabrication", "Parallel with receiving.", parent="2.0"),
        _task("MF-ASM", "Assembly station", 25, ["MF-RECV", "MF-FAB"], "assembly", "Joins the two upstream stations.", parent="3.0"),
        _task("MF-QA", "Quality station", 12, ["MF-ASM"], "quality", "Inspection.", parent="3.0"),
        _task("MF-PACK", "Packaging and ship", 10, ["MF-QA"], "shipping", "Outbound station.", parent="4.0"),
        _task("MF-RUN", "Production ready", 0, ["MF-PACK"], "shipping", "Readiness milestone.", milestone=True, parent="4.0"),
    ]
    people = {task.id: 4 for task in tasks if not task.milestone}
    return _effort_plan(
        "manufacturing",
        "Manufacturing template represented as production stations and a joining assembly step.",
        [_wbs("1.0", "Layout"), _wbs("2.0", "Stations"), _wbs("3.0", "Assembly"), _wbs("4.0", "Release")],
        tasks,
        [ResourcePool("technicians", "Technicians", 8, "labor", "person", 480)],
        [_risk("R1", "Station balance is untested", "Cycle times are placeholders.", "schedule", 0.4, 15000, 12)],
        ["Station list", "Flow schedule", "Sample cost", "Line diagram"],
        ["layout", "receiving", "fabrication", "assembly", "quality", "shipping"],
        people,
        daily_rate=480,
    )


def _infrastructure(values: dict) -> PlanDraft:
    tasks = [
        _task("IN-SURV", "Survey", 20, [], "survey", "Alignment survey allowance.", parent="1.0"),
        _task("IN-SEG1", "Segment A", 40, ["IN-SURV"], "alignment", "First segment.", parent="2.0"),
        _task("IN-SEG2", "Segment B", 45, ["IN-SEG1"], "alignment", "Second segment follows the first.", parent="2.0"),
        _task("IN-SEG3", "Segment C", 35, ["IN-SEG1"], "alignment", "Parallel segment after A.", parent="2.0"),
        _task("IN-SYS", "Systems", 30, ["IN-SEG2", "IN-SEG3"], "systems", "Depends on both remaining segments.", parent="3.0"),
        _task("IN-OPEN", "Open for use", 0, ["IN-SYS"], "closeout", "Opening milestone.", milestone=True, parent="3.0"),
    ]
    people = {task.id: 6 for task in tasks if not task.milestone}
    return _effort_plan(
        "infrastructure",
        "Infrastructure template as a linear alignment with one parallel segment.",
        [_wbs("1.0", "Survey"), _wbs("2.0", "Alignment"), _wbs("3.0", "Opening")],
        tasks,
        [ResourcePool("crews", "Field crews", 3, "labor", "crew", 2400)],
        [_risk("R1", "Access constraints unknown", "No site access window was provided.", "schedule", 0.5, 50000, 20)],
        ["Segment schedule", "Sample cost", "Alignment diagram"],
        ["survey", "alignment", "systems", "closeout"],
        people,
        daily_rate=700,
        services_lump=15000,
    )


def _urban(values: dict) -> PlanDraft:
    tasks = [
        _task("UR-PLAN", "District framework", 25, [], "framework", "Planning framework.", parent="1.0"),
        _task("UR-BLK1", "Block A", 40, ["UR-PLAN"], "blocks", "First block.", parent="2.0"),
        _task("UR-BLK2", "Block B", 36, ["UR-PLAN"], "blocks", "Second block, parallel with A.", parent="2.0"),
        _task("UR-PUB", "Public realm", 30, ["UR-BLK1", "UR-BLK2"], "public", "Connects the blocks.", parent="3.0"),
        _task("UR-DONE", "Framework issued", 0, ["UR-PUB"], "closeout", "Issue milestone.", milestone=True, parent="3.0"),
    ]
    people = {task.id: 5 for task in tasks if not task.milestone}
    return _effort_plan(
        "urban",
        "Urban template as district blocks and a shared public-realm package.",
        [_wbs("1.0", "Framework"), _wbs("2.0", "Blocks"), _wbs("3.0", "Public realm")],
        tasks,
        [ResourcePool("planners", "Planning team", 5, "labor", "person", 700)],
        [_risk("R1", "Land control is not confirmed", "No parcel status was provided.", "scope", 0.6, 0, 30)],
        ["Block plan", "Sample cost", "District diagram"],
        ["framework", "blocks", "public", "closeout"],
        people,
        daily_rate=700,
    )


def _logistics(values: dict) -> PlanDraft:
    tasks = [
        _task("LG-WH", "Warehouse readiness", 20, [], "warehouse", "Origin facility.", parent="1.0"),
        _task("LG-HUB", "Hub activation", 18, [], "hub", "Parallel hub setup.", parent="1.0"),
        _task("LG-LANE", "Primary lane", 15, ["LG-WH", "LG-HUB"], "lane", "Requires both nodes.", parent="2.0"),
        _task("LG-LAST", "Last-mile node", 12, ["LG-HUB"], "last-mile", "Can start before the primary lane finishes.", parent="2.0"),
        _task("LG-GO", "Network open", 0, ["LG-LANE", "LG-LAST"], "closeout", "Opening milestone.", milestone=True, parent="3.0"),
    ]
    people = {task.id: 4 for task in tasks if not task.milestone}
    return _effort_plan(
        "logistics",
        "Logistics template as facilities, a lane, and a distribution node.",
        [_wbs("1.0", "Nodes"), _wbs("2.0", "Routes"), _wbs("3.0", "Opening")],
        tasks,
        [ResourcePool("operators", "Operators", 6, "labor", "person", 420)],
        [_risk("R1", "Carrier capacity is assumed", "No contracted capacity was provided.", "resource", 0.5, 25000, 10)],
        ["Node plan", "Lane schedule", "Network diagram"],
        ["warehouse", "hub", "lane", "last-mile", "closeout"],
        people,
        daily_rate=420,
    )


def _research(values: dict) -> PlanDraft:
    tasks = [
        _task("RD-Q", "Question and protocol", 15, [], "question", "Define the question.", parent="1.0"),
        _task("RD-EXP", "Experiment", 40, ["RD-Q"], "experiment", "Primary experiment window.", parent="2.0"),
        _task("RD-ANA", "Analysis", 20, ["RD-EXP"], "analysis", "Analysis after data exists.", parent="3.0"),
        _task("RD-REP", "Report", 10, ["RD-ANA"], "report", "Write-up.", parent="3.0"),
        _task("RD-DONE", "Findings issued", 0, ["RD-REP"], "report", "Issue milestone.", milestone=True, parent="3.0"),
    ]
    people = {task.id: 3 for task in tasks if not task.milestone}
    return _effort_plan(
        "research",
        "Research template as sequential layers from question through findings.",
        [_wbs("1.0", "Protocol"), _wbs("2.0", "Experiment"), _wbs("3.0", "Findings")],
        tasks,
        [ResourcePool("researchers", "Researchers", 4, "labor", "person", 700)],
        [_risk("R1", "Study duration is a placeholder", "No protocol was supplied.", "schedule", 0.55, 0, 20)],
        ["Phase plan", "Sample cost", "Layer diagram"],
        ["question", "experiment", "analysis", "report"],
        people,
        daily_rate=700,
    )


def _event(values: dict) -> PlanDraft:
    tasks = [
        _task("EV-VEN", "Venue hold", 10, [], "venue", "Venue placeholder.", parent="1.0"),
        _task("EV-PROG", "Program", 15, [], "program", "Parallel program design.", parent="1.0"),
        _task("EV-VEND", "Vendors", 12, ["EV-VEN"], "vendors", "Vendor setup after the venue hold.", parent="2.0"),
        _task("EV-RUN", "Event operations", 3, ["EV-PROG", "EV-VEND"], "operations", "Short operations window.", parent="3.0"),
        _task("EV-OPEN", "Doors open", 0, ["EV-RUN"], "operations", "Opening milestone.", milestone=True, parent="3.0"),
    ]
    people = {"EV-VEN": 2, "EV-PROG": 3, "EV-VEND": 3, "EV-RUN": 8}
    return _effort_plan(
        "event",
        "Event template as venue, program, vendors, and a short operations window.",
        [_wbs("1.0", "Setup"), _wbs("2.0", "Vendors"), _wbs("3.0", "Operations")],
        tasks,
        [ResourcePool("crew", "Event crew", 8, "labor", "person", 350)],
        [_risk("R1", "Attendance is unknown", "No capacity figure was supplied.", "scope", 0.4, 5000, 0)],
        ["Run of show", "Sample cost", "Zone diagram"],
        ["venue", "program", "vendors", "operations"],
        people,
        daily_rate=350,
        services_lump=4000,
    )


def _custom(values: dict) -> PlanDraft:
    tasks = [
        _task("CU-DEF", "Define outcomes", 10, [], "define", "Custom phase.", parent="1.0"),
        _task("CU-A", "Workstream A", 20, ["CU-DEF"], "build", "Parallel workstream.", parent="2.0", scalable=True),
        _task("CU-B", "Workstream B", 18, ["CU-DEF"], "build", "Parallel workstream.", parent="2.0", scalable=True),
        _task("CU-JOIN", "Integrate", 8, ["CU-A", "CU-B"], "integrate", "Join point.", parent="3.0"),
        _task("CU-DONE", "Complete", 0, ["CU-JOIN"], "closeout", "Completion milestone.", milestone=True, parent="3.0"),
    ]
    people = {task.id: 3 for task in tasks if not task.milestone}
    draft = _effort_plan(
        "custom",
        "Custom projects use a generic phase-block metaphor. The blocks are planning containers, not a physical design.",
        [_wbs("1.0", "Definition"), _wbs("2.0", "Workstreams"), _wbs("3.0", "Integration")],
        tasks,
        [ResourcePool("team", "Project team", float(values.get("team_size") or 4), "labor", "person", 650)],
        [_risk("R1", "Scope is only the prompt", "No detailed brief was supplied.", "scope", 0.6, 0, 15)],
        ["Phase plan", "Sample cost", "Conceptual phase blocks"],
        ["define", "build", "integrate", "closeout"],
        people,
    )
    draft.scene["label"] = "Conceptual phase blocks"
    return draft


def _risk(code, title, description, category, probability, impact_cost, impact_days) -> dict:
    return {
        "code": code,
        "title": title,
        "description": description,
        "category": category,
        "probability": probability,
        "impact_cost": impact_cost,
        "impact_schedule_days": impact_days,
        "mitigation": "Replace the placeholder once the missing fact is known.",
        "status": "open",
    }
