import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("API_KEY", "")
    from app.db import reset_database_state

    reset_database_state()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def prod_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'prod.db'}")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "accounts")
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "admin-password-123")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    from app.db import get_engine, reset_database_state
    from app.models import Base

    reset_database_state()
    Base.metadata.create_all(bind=get_engine())
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def accounts_client(tmp_path, monkeypatch):
    """Development app env with real accounts (cookies over plain http for the test client)."""

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "accounts")
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "Admin@Example.com")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "admin-password-123")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("LOGIN_MAX_FAILURES", "3")
    from app.db import reset_database_state

    reset_database_state()
    from app.api import auth_routes

    auth_routes._limiters.clear()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
