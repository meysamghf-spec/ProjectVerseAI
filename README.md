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
docker-compose.yml       Production stack (behind a shared Caddy, no host ports)
docker-compose.dev.yml   Local stack on 127.0.0.1
docker-compose.shared-db.yml  Optional overlay for a shared PostgreSQL
deploy/Caddyfile.shared.example  Site block for the shared Caddy
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

Open http://localhost:3000. The dashboard can create the residential tower demonstration without signing in (development mode). Non-production startup also calls `create_all`, so a fresh SQLite file works even before the first Alembic run. Use Alembic whenever the schema must match migration history, including Docker and production.

## Docker Compose

Local, development mode, ports bound to 127.0.0.1 only:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Production (`docker-compose.yml`, profile `production`) publishes no host ports. It joins the server's shared Caddy network and requires secrets from `.env`. See [DEPLOY.md](DEPLOY.md) for the full Iranian VPS guide (shared Caddy, optional shared PostgreSQL, Iranian Docker/PyPI/npm mirrors, first admin, health checks, backups).

## Environment variables

Copy `.env.example`; it documents every variable. The main ones:

| Variable | Role |
| --- | --- |
| `APP_ENV` | `development` or `production`. Production hides internal error text, skips `create_all`, and enforces the checks below. |
| `AUTH_MODE` | `accounts` (required in production), `development` (shared owner header), or `api_key` (legacy, development only). |
| `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD` | First administrator, created only while the users table is empty. |
| `SESSION_HOURS`, `COOKIE_SECURE` | Session lifetime (default 12 h). Cookies are `Secure` in production unless overridden. |
| `DATABASE_URL` / `POSTGRES_PASSWORD` | Database. Production rejects passwords under 16 characters. |
| `CORS_ORIGINS` | Explicit browser origins. Production compose sets `https://$SITE_ADDRESS`. |
| `SITE_ADDRESS`, `PROXY_NETWORK` | Public hostname and the shared Caddy network (default `caddy`). |
| `DEFAULT_LOCALE` / `NEXT_PUBLIC_DEFAULT_LOCALE` | Interface language for first-time visitors: `en` (default) or `fa`. |
| `PYTHON_IMAGE`, `NODE_IMAGE`, `POSTGRES_IMAGE`, `PIP_INDEX_URL`, `NPM_REGISTRY` | Optional mirrors for image builds. |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | Optional OpenAI-compatible extractor. Read from the environment, never hard-coded. |
| `NEXT_PUBLIC_API_URL` | Browser-facing API origin. Empty means same origin (production behind Caddy). |

## Authentication

Production uses **user accounts** (`AUTH_MODE=accounts`). There is no public sign-up: the first admin comes from `INITIAL_ADMIN_*`, and admins create further users on the **Users** page or with `python -m app.cli create-user`. Roles are `admin` and `user`. Passwords are scrypt hashes; sessions are random tokens stored hashed in the database and sent as an `HttpOnly`, `SameSite=Lax` cookie (or `Authorization: Bearer` for scripts). Cookie-authenticated writes and sign-in require an `X-Requested-With` header. Failed sign-ins are throttled per email and client address. Every user sees only their own projects.

Development mode is not an account system. The UI sends `X-Owner-Id` (default `dev-user`), which can be spoofed; production ignores it. Production also rejects `api_key` and `development` modes, wildcard CORS, and short database passwords.

## Language and formatting

The UI defaults to English (LTR, Gregorian dates, USD by default) and has an English/فارسی toggle in the header. Persian switches to RTL, Jalali dates (date inputs accept ۱۴۰۵/۰۷/۲۴), Persian digits, and toman or rial for IRR (Settings). The choice persists in `localStorage` and a cookie. The API stores text as UTF-8; project search normalizes Arabic/Persian yeh and kaf, Persian/Arabic digits, and ZWNJ. The deterministic extractor understands Persian descriptions (طبقه، زیرزمین، متر مربع، میلیارد تومان، ماه، نفر). Some detailed project screens are still English-only.

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

- No password reset by email, email verification, or two-factor sign-in. The sign-in throttle is in memory.
- Cost sample rates are in USD; non-USD projects need a USD exchange rate to convert estimates (otherwise a warning is shown).
- Cost rates are configurable sample assumptions. There is no validated price database.
- The 3D view is a conceptual massing or diagram driven by project parameters. It is not a BIM model, structural analysis, or architectural drawing.
- The default calendar counts elapsed calendar days. Weekend and holiday calendars exist in the engine and are off unless a project turns them on.
- Background simulation uses threads inside the API process. It is not a durable external queue.
- Docker images and Compose are provided. This repository does not deploy them to a hosted environment by itself.
