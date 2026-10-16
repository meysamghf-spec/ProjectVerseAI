"""Persian text end to end: extraction, storage (UTF-8), search normalization, and currency."""

import os
import uuid

import pytest
from app.engine.extractor import extract_requirements
from app.text import normalize_digits, normalize_for_search

PERSIAN_PROMPT = (
    "ساخت یک ساختمان مسکونی ۱۲ طبقه با ۲ طبقه زیرزمین، ۹٬۶۰۰ متر مربع زیربنا، "
    "بودجه ۱۵۰ میلیارد تومان و مدت ۲۴ ماه در اراک با تیم ۴۰ نفر"
)


def test_normalization():
    assert normalize_digits("۱۲۳٬۴۵۶٫۵") == "123,456.5"
    assert normalize_for_search("علي  كاظمي") == normalize_for_search("علی کاظمی")
    assert normalize_for_search("نرم‌افزار") == "نرم افزار"
    assert normalize_for_search("Tower") == "tower"


def test_persian_prompt_is_extracted():
    values = extract_requirements(PERSIAN_PROMPT).values
    assert values["project_type"] == "construction"
    assert values["floors"] == 12
    assert values["basements"] == 2
    assert values["gfa_sqm"] == 9600
    assert values["budget_amount"] == 150_000_000_000 * 10  # toman stored as rial
    assert values["currency"] == "IRR"
    assert values["duration_months"] == 24
    assert values["team_size"] == 40


@pytest.mark.parametrize(
    ("prompt", "amount", "currency"),
    [
        ("بودجه ۵۰۰ میلیون ریال", 500_000_000, "IRR"),
        ("بودجه ۲ همت", 2e12 * 10, "IRR"),
        ("بودجه ۳ میلیون دلار برای پل", 3_000_000, "USD"),
    ],
)
def test_persian_money(prompt, amount, currency):
    values = extract_requirements(prompt).values
    assert values["budget_amount"] == amount
    assert values["currency"] == currency


def test_english_prompt_unchanged():
    values = extract_requirements(
        "Plan a 20-story residential building with three basement parking levels, 25,000 square meters, "
        "a $15 million budget, and a 30-month schedule."
    ).values
    assert (values["floors"], values["basements"], values["gfa_sqm"]) == (20, 3, 25000)
    assert (values["budget_amount"], values["currency"], values["duration_months"]) == (15_000_000, "USD", 30)


def _db_client(request, tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'fa.db'}" if request.param == "sqlite" else os.environ["DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "development")
    from app.db import get_engine, reset_database_state
    from app.models import Base

    reset_database_state()
    Base.metadata.create_all(bind=get_engine())
    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


_BACKENDS = ["sqlite"] + (["postgresql"] if os.getenv("DATABASE_URL", "").startswith("postgresql") else [])


@pytest.fixture(params=_BACKENDS)
def any_client(request, tmp_path, monkeypatch):
    with _db_client(request, tmp_path, monkeypatch) as client:
        yield client


def test_persian_project_roundtrip_and_search(any_client):
    owner = {"X-Owner-Id": f"fa-test-{uuid.uuid4().hex}"}  # isolated from earlier runs on a shared Postgres
    created = any_client.post(
        "/api/v1/projects",
        json={"prompt": PERSIAN_PROMPT, "name": "برج مسکونی اراک", "location": "اراک، استان مركزي", "generate": True},
        headers=owner,
    )
    assert created.status_code == 201, created.text
    project = created.json()
    reopened = any_client.get(f"/api/v1/projects/{project['id']}", headers=owner).json()
    assert reopened["name"] == "برج مسکونی اراک"
    assert reopened["currency"] == "IRR"
    any_client.post("/api/v1/projects", json={"prompt": "Software app 3 months", "name": "Other"}, headers=owner)
    # Arabic yeh/kaf in the query and Persian letters in the data (and vice versa) still match.
    for query in ("برج", "مسكوني", "مرکزی", "اراك"):
        found = any_client.get("/api/v1/projects", params={"q": query}, headers=owner).json()
        assert found["total"] == 1, query
        assert found["items"][0]["id"] == project["id"]
    assert any_client.get("/api/v1/projects", params={"q": "نیست"}, headers=owner).json()["total"] == 0
    assert any_client.get("/api/v1/projects", headers=owner).json()["total"] == 2
    any_client.delete(f"/api/v1/projects/{project['id']}", headers=owner)


def test_non_usd_costs_are_flagged_or_converted(any_client):
    owner = {"X-Owner-Id": "fx-owner"}
    body = {"prompt": "ساختمان مسکونی ۴ طبقه ۳۲۰۰ متر مربع", "currency": "IRR", "generate": True}
    unconverted = any_client.post("/api/v1/projects", json=body, headers=owner).json()
    converted = any_client.post("/api/v1/projects", json={**body, "usd_exchange_rate": 1_000_000}, headers=owner).json()
    a = any_client.get(f"/api/v1/projects/{unconverted['id']}", headers=owner).json()
    b = any_client.get(f"/api/v1/projects/{converted['id']}", headers=owner).json()
    assert any("NOT converted to IRR" in warning for warning in a["plan_warnings"])
    assert not any("NOT converted" in warning for warning in b["plan_warnings"])
    assert any(item["key"] == "usd_exchange_rate" for item in b["assumptions"])
    total_a = a["cost_summary"]["total"]
    total_b = b["cost_summary"]["total"]
    assert total_b == pytest.approx(total_a * 1_000_000, rel=1e-6)
