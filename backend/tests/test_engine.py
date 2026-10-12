"""Known-answer tests for the deterministic engine."""

from datetime import date

from app.engine.budget import aggregate_costs
from app.engine.calendar import add_days, inclusive_finish
from app.engine.costs import construction_cost_lines
from app.engine.curves import cumulative_cost
from app.engine.distributions import percentile
from app.engine.extractor import extract_requirements
from app.engine.monte_carlo import CostModel, run_monte_carlo
from app.engine.planner import generate_plan
from app.engine.resources import analyze_resources
from app.engine.scenarios import ScenarioPatch, apply_scenario, recompute_percent_costs
from app.engine.scheduler import schedule_tasks
from app.engine.types import CostLine, ResourceDemand, ResourcePool, SchedTask, WorkCalendar
from app.engine.validation import validate_plan


def _task(task_id, duration, deps=None, **kwargs):
    return SchedTask(id=task_id, name=task_id, duration=duration, dependencies=deps or [], **kwargs)


def test_critical_path_and_parallel_tasks():
    tasks = [
        _task("A", 5),
        _task("B", 3, ["A"]),
        _task("C", 4),
        _task("D", 2, ["B", "C"]),
    ]
    result = schedule_tasks(tasks, project_start=date(2026, 1, 5))
    assert result.ok
    by_id = {task.id: task for task in result.tasks}
    assert result.project_duration == 10
    assert by_id["A"].earliest_start == 0
    assert by_id["C"].earliest_start == 0
    assert by_id["B"].earliest_start == 5
    assert by_id["D"].earliest_start == 8
    assert by_id["C"].total_float == 4
    assert by_id["A"].is_critical
    assert by_id["B"].is_critical
    assert by_id["D"].is_critical
    assert not by_id["C"].is_critical
    assert result.critical_path == ["A", "B", "D"]
    assert by_id["A"].start_date == date(2026, 1, 5)
    assert by_id["A"].finish_date == date(2026, 1, 9)


def test_cycle_and_missing_dependency_and_bad_duration():
    cycle = schedule_tasks([_task("A", 2, ["B"]), _task("B", 2, ["A"])])
    assert not cycle.ok
    assert "cycle" in cycle.errors[0].lower()
    missing = schedule_tasks([_task("A", 2, ["Z"])])
    assert any("missing" in error.lower() for error in missing.errors)
    invalid = schedule_tasks([_task("A", 0)])
    assert any("zero duration" in error.lower() for error in invalid.errors)
    negative = schedule_tasks([_task("A", -1)])
    assert any("negative" in error.lower() for error in negative.errors)
    self_loop = schedule_tasks([_task("A", 1, ["A"])])
    assert not self_loop.ok


def test_weekend_calendar_skips_non_working_days():
    calendar = WorkCalendar(skip_weekends=True)
    monday = date(2026, 1, 5)
    assert add_days(monday, 5, calendar) == date(2026, 1, 12)
    assert inclusive_finish(monday, 5, calendar) == date(2026, 1, 9)
    friday = date(2026, 1, 9)
    assert inclusive_finish(friday, 2, calendar) == date(2026, 1, 12)


def test_budget_excludes_rollups_and_reports_variance():
    lines = [
        CostLine("labor", "Labor", "labor", 40, task_id="A"),
        CostLine("materials", "Materials", "materials", 60, task_id="B"),
        CostLine("rollup", "Parent rollup", "other", 100, include_in_total=False, notes="display only"),
    ]
    result = aggregate_costs(lines, budget=120)
    assert result.total == 100
    assert result.variance == 20
    assert not result.overrun
    assert result.excluded_line_ids == ["rollup"]
    over = aggregate_costs(lines, budget=90)
    assert over.overrun
    assert over.variance == -10


def test_negative_cost_is_rejected():
    try:
        aggregate_costs([CostLine("bad", "Bad", "labor", -5)])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "negative" in str(exc).lower()


def test_resource_conflict_only_when_tasks_overlap():
    tasks = [
        _task("A", 5, resources=[ResourceDemand("crew", 2)]),
        _task("B", 4, resources=[ResourceDemand("crew", 2)]),
    ]
    scheduled = schedule_tasks(tasks)
    pools = [ResourcePool("crew", "Crew", 2)]
    analysis = analyze_resources(scheduled.tasks, tasks, pools)
    assert analysis.resources[0].overloaded
    assert analysis.conflicts
    sequential = [
        _task("A", 5, resources=[ResourceDemand("crew", 2)]),
        _task("B", 4, ["A"], resources=[ResourceDemand("crew", 2)]),
    ]
    scheduled = schedule_tasks(sequential)
    analysis = analyze_resources(scheduled.tasks, sequential, pools)
    assert not analysis.resources[0].overloaded


def test_percentile_matches_linear_interpolation():
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([1, 2, 3, 4, 5], 80) == 4.2
    assert percentile([1, 2, 3, 4, 5], 90) == 4.6


def test_monte_carlo_is_seeded_dependency_aware_and_exact_when_deterministic():
    tasks = [
        _task("A", 5, duration_min=5, duration_mode=5, duration_max=5),
        _task("B", 3, ["A"], duration_min=3, duration_mode=3, duration_max=3),
        _task("C", 4, duration_min=4, duration_mode=4, duration_max=4),
    ]
    lines = [CostLine("direct", "Direct", "labor", 100, amount_min=100, amount_mode=100, amount_max=100)]
    model = CostModel(overhead_pct=0.1, contingency_pct=0.1, direct_lines=lines)
    first = run_monte_carlo(tasks, seed=7, iterations=40, cost_model=model, deadline_day=20, budget=200)
    second = run_monte_carlo(tasks, seed=7, iterations=40, cost_model=model, deadline_day=20, budget=200)
    assert first.duration_samples == second.duration_samples
    assert first.cost_samples == second.cost_samples
    assert first.p50_duration == percentile(first.duration_samples, 50)
    assert first.p80_duration == percentile(first.duration_samples, 80)
    assert first.p90_duration == percentile(first.duration_samples, 90)
    assert first.p50_duration == 8
    assert abs(first.p50_cost - 121) < 1e-6
    assert first.deadline_probability == 1
    assert first.budget_probability == 1
    late = run_monte_carlo(tasks, seed=7, iterations=40, cost_model=model, deadline_day=1, budget=10)
    assert late.deadline_probability == 0
    assert late.budget_probability == 0
    uncertain = [
        _task("A", 5, duration_min=2, duration_mode=5, duration_max=9),
    ]
    varied = run_monte_carlo(uncertain, seed=3, iterations=80, cost_model=model, deadline_day=5)
    other_seed = run_monte_carlo(uncertain, seed=4, iterations=80, cost_model=model, deadline_day=5)
    assert varied.duration_samples != other_seed.duration_samples
    assert varied.p50_duration <= varied.p80_duration <= varied.p90_duration
    assert 0 <= varied.deadline_probability <= 1
    assert varied.schedule_contributors[0]["id"] == "A"


def test_monte_carlo_rejects_bad_inputs():
    try:
        run_monte_carlo([_task("A", 1)], seed=1, iterations=1)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    try:
        run_monte_carlo(
            [_task("A", 5, duration_min=8, duration_mode=5, duration_max=4)],
            seed=1,
            iterations=10,
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "triangular" in str(exc).lower()


def test_prompt_extraction_separates_facts_from_assumptions():
    prompt = (
        "Plan a 20-story residential building with three basement parking levels, "
        "25,000 square meters of gross floor area, a $15 million budget, and a "
        "30-month construction schedule."
    )
    extraction = extract_requirements(prompt, today=date(2026, 1, 5))
    assert extraction.project_type == "construction"
    known = {item.key: item.value for item in extraction.known}
    assert known["floors"] == 20
    assert known["basements"] == 3
    assert known["gfa_sqm"] == 25000
    assert known["budget_amount"] == 15_000_000
    assert known["currency"] == "USD"
    assert known["duration_months"] == 30
    assumption_keys = {item.key for item in extraction.assumptions}
    assert "floor_to_floor_height_m" in assumption_keys
    assert "location" in extraction.missing
    assert "start_date" in extraction.missing
    assert extraction.values["floors"] == 20
    assert all(item.origin != "user" or item.key in known for item in extraction.assumptions)
    overridden = extract_requirements(prompt, {"floors": 10, "category": "construction"})
    assert overridden.values["floors"] == 10
    assert any(item.key == "floors" and item.origin == "user" and item.value == 10 for item in overridden.known)
    sparse = extract_requirements("Help me plan something unusual.", today=date(2026, 1, 5))
    assert sparse.project_type == "custom"
    assert sparse.missing
    assert sparse.assumptions


def test_construction_plan_matches_demo_critical_path_and_cost_formula():
    values = {
        "project_type": "construction",
        "floors": 20,
        "basements": 3,
        "gfa_sqm": 25000,
        "budget_amount": 15_000_000,
    }
    draft = generate_plan(values)
    schedule = schedule_tasks(draft.tasks)
    assert schedule.ok
    assert schedule.project_duration == 900
    assert "CON-SUPER" in schedule.critical_path
    assert "CON-MEP" not in schedule.critical_path
    assert "CON-ENV" in schedule.critical_path
    lines, model = construction_cost_lines(25000, 20, 3)
    direct = 25000 * (180 + 160 + 55 + 40) + 8 * 40000 + 3 * 250000
    overhead = direct * 0.12
    contingency = (direct + overhead) * 0.08
    total = aggregate_costs(lines, 15_000_000)
    assert abs(total.total - (direct + overhead + contingency)) < 0.05
    assert total.variance > 0
    assert model["direct_line_ids"]
    assert draft.scene["floors"] == 20
    assert draft.scene["basements"] == 3
    assert draft.scene["metaphor"] == "procedural-building"
    assert "not an architectural" in draft.scene["disclaimer"].lower() or "not an architectural" in draft.scene["disclaimer"]


def test_scenario_does_not_mutate_baseline_and_scales_only_configured_tasks():
    draft = generate_plan(
        {"project_type": "construction", "floors": 20, "basements": 3, "gfa_sqm": 25000, "budget_amount": 15_000_000}
    )
    original = {task.id: task.duration for task in draft.tasks}
    patch = ScenarioPatch(
        name="crew",
        description="more crews",
        duration_factors={"superstructure": 0.8929, "interiors": 0.8929},
        scalable_only=True,
        scalable_phases=["superstructure", "interiors"],
    )
    patched, costs, notes = apply_scenario(draft.tasks, draft.costs, patch)
    assert {task.id: task.duration for task in draft.tasks} == original
    by_id = {task.id: task for task in patched}
    assert by_id["CON-SUPER"].duration == round(300 * 0.8929, 4)
    assert by_id["CON-INT"].duration < 156
    assert by_id["CON-ENV"].duration == 120
    assert by_id["CON-MEP"].duration == 100
    assert notes
    scaled, scaled_costs, _notes = apply_scenario(
        draft.tasks,
        costs,
        ScenarioPatch(name="prices", description="materials", cost_category_factors={"materials": 1.15}),
    )
    assert scaled[0].duration == draft.tasks[0].duration
    updated = recompute_percent_costs(scaled_costs, 0.12, 0.08)
    base_materials = sum(line.amount for line in draft.costs if line.category == "materials")
    new_materials = sum(line.amount for line in updated if line.category == "materials")
    assert abs(new_materials - base_materials * 1.15) < 0.05


def test_facade_overlap_shortens_schedule_and_overloads_crane():
    draft = generate_plan(
        {"project_type": "construction", "floors": 20, "basements": 3, "gfa_sqm": 25000}
    )
    patched, _costs, _notes = apply_scenario(
        draft.tasks,
        draft.costs,
        ScenarioPatch(name="facade", description="overlap", lag_overrides=[("CON-ENV", "CON-SUPER", -120)]),
    )
    baseline = schedule_tasks(draft.tasks)
    overlapped = schedule_tasks(patched)
    assert overlapped.project_duration < baseline.project_duration
    pools = [ResourcePool(pool.id, pool.name, pool.available, pool.resource_type, pool.unit) for pool in draft.resources]
    analysis = analyze_resources(overlapped.tasks, patched, pools)
    assert any("crane" in conflict.lower() for conflict in analysis.conflicts)


def test_cumulative_cost_ends_at_the_phase_total():
    tasks = schedule_tasks([_task("A", 10, phase="build"), _task("B", 10, ["A"], phase="finish")]).tasks
    curve = cumulative_cost(tasks, {"build": 40, "finish": 60, "overhead": 10})
    assert curve[-1]["cost"] == 110
    assert curve[0]["cost"] < curve[-1]["cost"]


def test_validation_warns_on_budget_and_deadline_without_blocking_warnings_only():
    tasks = [_task("A", 10), _task("B", 10, ["A"])]
    costs = [CostLine("c", "Cost", "labor", 500)]
    result = validate_plan(
        tasks,
        costs,
        [],
        start=date(2026, 1, 1),
        deadline=date(2026, 1, 10),
        budget=100,
    )
    assert result["schedule_ok"]
    assert any("budget" in warning.lower() for warning in result["warnings"])
    assert any("deadline" in warning.lower() or "window" in warning.lower() for warning in result["warnings"])
    assert result["can_continue"]


def test_other_project_types_schedule():
    for project_type in (
        "software",
        "manufacturing",
        "infrastructure",
        "urban",
        "logistics",
        "research",
        "event",
        "custom",
    ):
        draft = generate_plan({"project_type": project_type, "team_size": 6})
        result = schedule_tasks(draft.tasks)
        assert result.ok, project_type
        assert result.project_duration > 0
        assert draft.scene["metaphor"] != "procedural-building"
        total = aggregate_costs(draft.costs)
        assert total.total > 0
