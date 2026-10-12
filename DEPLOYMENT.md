# Deployment

ProjectVerse AI can be self-hosted with Docker Compose. This repository does not subscribe to a hosting provider and does not publish a live URL. Use the steps below on a machine you control. Do not commit the API key or database password.

## What you need

- Docker Engine and Docker Compose 2.24 or newer (`ports: !reset` in the production overlay).
- A public hostname for the site and a public hostname for the API, or one host with two ports.
- A long random `API_KEY`. This is a shared service key, not a user-account system.

## Production configuration

Create a `.env` file next to `docker-compose.yml`. Keep it out of git.

```bash
API_KEY=replace-with-a-long-random-value
API_OWNER_ID=hosted-owner
CORS_ORIGINS=https://projects.example.com
NEXT_PUBLIC_API_URL=https://api.example.com
```

`NEXT_PUBLIC_API_URL` is baked into the frontend at image build time. Changing it later requires a frontend rebuild.

Start the stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

The API container runs `alembic upgrade head` before uvicorn. The production overlay sets `APP_ENV=production` and `AUTH_MODE=api_key`, and it stops publishing PostgreSQL on the host. The base Compose file still contains the local database password `projectverse`. Change `POSTGRES_PASSWORD` and `DATABASE_URL` together before exposing the host to the internet.

The browser calls the API directly. Put TLS in front of ports 3000 and 8000, and set `CORS_ORIGINS` to the exact site origin. A wildcard origin is rejected in production. Health checks:

- `GET /api/v1/health` returns `{"status":"ok"}` without a key.
- `GET /api/v1/ready` returns 200 when the database answers `SELECT 1`.
- Project routes without `X-API-Key` or `Authorization: Bearer` return 401.

The UI stores the key in `localStorage` under `projectverse.apiKey` from the Settings page. Anyone with that key can read the single production owner’s projects. Add a real account system before offering this to untrusted users.

## Migrations

From a backend checkout pointed at the production database:

```bash
cd backend
DATABASE_URL=postgresql+psycopg://projectverse:projectverse@db:5432/projectverse \
  python3 -m alembic upgrade head
```

The Compose command already does this on API startup. Run it yourself when you want to migrate without restarting the process.

## Smoke test

After the API is listening:

```bash
python3 scripts/smoke_api.py http://127.0.0.1:8000
```

The script checks health, readiness, project creation, reopening, a generated schedule, owner isolation, a JSON report, and deletion. Development mode accepts `X-Owner-Id`. Against production, export the key and send it yourself; the script is the development-mode procedure. A production check is:

```bash
curl -sf http://127.0.0.1:8000/api/v1/health
curl -sf -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/v1/projects
# expect 401
curl -sf -H "X-API-Key: $API_KEY" http://127.0.0.1:8000/api/v1/projects
```

Then open the site, load the residential tower demonstration, and confirm the 3D view, schedule, and a PDF download.

## What this environment did not do

No hosting account, DNS name, or TLS certificate was available, and paid hosting was not authorized. The application is not publicly deployed.
