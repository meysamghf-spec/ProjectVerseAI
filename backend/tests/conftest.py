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
    monkeypatch.setenv("AUTH_MODE", "api_key")
    monkeypatch.setenv("API_KEY", "test-key")
    from app.db import get_engine, reset_database_state
    from app.models import Base

    reset_database_state()
    Base.metadata.create_all(bind=get_engine())
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
