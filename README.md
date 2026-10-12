# ProjectVerse AI

ProjectVerse AI turns a natural-language project description into a structured plan, a dependency-aware schedule, a budget built from stored cost lines, a resource check, a risk register, seeded uncertainty runs, scenario comparisons, downloadable reports, and a conceptual 3D scene.

The default path is fully local. Scheduling, cost aggregation, critical path, and Monte Carlo math run in deterministic Python. An optional language-model adapter can suggest requirement hints, but it never owns those calculations and the app does not need an API key.

Figures in this product are planning-model outputs. They are not quotations, market prices, or engineering certifications.

## Repository layout

```
backend/                 FastAPI application, simulation engine, Alembic
  app/engine/            Pure scheduling, cost, resource, and Monte Carlo code
  app/services/          Persistence, jobs, reports, demo seed
  app/api/routes.py      /api/v1
  alembic/               Database migrations
  tests/                 Engine, API, and migration tests
frontend/                Next.js workspace and React Three Fiber scenes
  lib/scene.ts           Procedural scene builder used by the canvas and tests
  app/projects/[id]/     Schedule, budget, resources, risks, scenarios, reports
docker-compose.yml       PostgreSQL, API, and web UI
.github/workflows/ci.yml Backend and frontend checks
```

## Local development

Python 3.11+ and Node.js 22 are the versions exercised here. SQLite is the default database.

```bash
cd backend
python3 -m pip install -r requirements-dev.txt
python3 -m alembic upgrade head
python3 -m uvicorn app.main:app --reload --port 8000
```

In another shell:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. The dashboard can create the residential tower demonstration without an API key. Non-production startup also calls `create_all`, so a fresh SQLite file works even before the first Alembic run. Use Alembic whenever the schema must match migration history, including Docker and production.

## Docker Compose

```bash
docker compose up --build
```

Compose starts PostgreSQL 16, runs `alembic upgrade head` in the API container, and serves the UI on port 3000. The published database credentials in `docker-compose.yml` are local defaults only.

Public hosting steps, the production Compose overlay, and the live smoke test are in [DEPLOYMENT.md](DEPLOYMENT.md). This repository does not deploy itself to a hosted URL.

## Environment variables

Copy `.env.example` when you want overrides. Empty values are valid.

| Variable | Role |
| --- | --- |
| `APP_ENV` | `development` or `production`. Production hides internal error text and skips automatic `create_all`. |
| `AUTH_MODE` | `development` or `api_key`. |
| `DEV_OWNER_ID` | Owner id used when the `X-Owner-Id` header is absent in development. |
| `API_KEY` | Required when `AUTH_MODE=api_key`. Send `X-API-Key` or `Authorization: Bearer`. |
| `API_OWNER_ID` | Single owner id used for API-key mode. |
| `DATABASE_URL` | Default `sqlite:///./projectverse.db`. Compose uses PostgreSQL. |
| `CORS_ORIGINS` | Comma-separated browser origins. |
| `LLM_PROVIDER` | `deterministic` (default) or `openai_compatible`. |
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | Optional provider settings. Read from the environment, never hard-coded. |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` | Bounds for the optional provider. |
| `NEXT_PUBLIC_API_URL` | Browser-facing API origin. Default `http://localhost:8000`. |

## Authentication

Development mode is not an account system. The UI stores `projectverse.owner` in `localStorage` (default `dev-user`) and sends `X-Owner-Id`. That header is a convenience and can be spoofed. Projects are filtered by owner, and another owner receives 404.

Production mode (`APP_ENV=production`, `AUTH_MODE=api_key`) requires `API_KEY` and ignores `X-Owner-Id`. Requests without the key are rejected. This is a shared service key, not per-user authentication. If production is started with development authentication or an empty key, project routes return 401 instead of accepting the owner header. `CORS_ORIGINS` in production must list explicit site origins. A `*` origin is rejected.

## Demonstration project

`POST /api/v1/demo/residential-tower` or the dashboard button creates **Residential Tower Demonstration**:

- 20 above-ground floors and 3 basement levels
- 25,000 square meters gross floor area
- 15,000,000 USD illustrative budget
- 30-month target (a month is 30 calendar days in this model)

The seed also stores a deterministic schedule, a seeded Monte Carlo run (seed 42, 200 iterations), and three scenarios: more structure workforce, higher material prices, and an accelerated facade overlap. Workforce changes do not automatically shorten every task. Only tasks marked scalable receive an explicit duration factor.

Sample unit rates are labeled `projectverse-sample-assumptions` and dated 2026-01-01. They are not live prices.

## API

Interactive docs are at `/docs`. Versioned routes live under `/api/v1`, including projects, extraction, plan generation, tasks, dependencies, schedule, budget, resources, risks, simulations, scenarios, comparison, reports, `/health`, and `/ready`.

Simulation requests accept `wait=true` for a short inline run. `wait=false` queues work on an in-process thread pool. A process restart marks queued or running rows as failed.

Reports return JSON, CSV, PDF, or XLSX generated from persisted results. CSV cells that begin with formula characters are prefixed so spreadsheet applications do not execute them.

## Tests and CI

```bash
cd backend && python3 -m ruff check app tests && python3 -m pytest -q
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

GitHub Actions (`.github/workflows/ci.yml`) runs those commands. It does not deploy the application.

## Optional language model

`LLM_PROVIDER=openai_compatible` sends the prompt to an OpenAI-compatible chat endpoint and accepts only allowlisted JSON fields. User-supplied structured fields override model hints. If the call fails or no key is configured, extraction falls back to the local parser and records that fallback. Generated text is never executed.

## Limitations

- Development authentication is a shared owner header, not accounts, sessions, or authorization reviews.
- Cost rates are configurable sample assumptions. There is no validated price database.
- The 3D view is a conceptual massing or diagram driven by project parameters. It is not a BIM model, structural analysis, or architectural drawing.
- The default calendar counts elapsed calendar days. Weekend and holiday calendars exist in the engine and are off unless a project turns them on.
- Background simulation uses threads inside the API process. It is not a durable external queue.
- One API key represents one owner in production mode.
- Docker images and Compose are provided. This repository does not deploy them to a hosted environment by itself.
