"""The checked-in migration must create the application schema."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_tables(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    from app.config import reset_settings_cache

    reset_settings_cache()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    expected = {
        "projects",
        "project_specifications",
        "tasks",
        "task_dependencies",
        "resources",
        "resource_assignments",
        "cost_items",
        "milestones",
        "risks",
        "assumptions",
        "scenarios",
        "simulation_runs",
        "simulation_results",
        "reports",
        "project_changes",
        "users",
        "auth_sessions",
    }
    assert expected <= tables
