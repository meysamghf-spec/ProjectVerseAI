# Deployment

Production deployment (Iranian VPS, shared Caddy, user accounts, health checks, mirrors) is described in [DEPLOY.md](DEPLOY.md).

## Live API smoke test (development mode)

```bash
cd backend
APP_ENV=development AUTH_MODE=development DATABASE_URL=sqlite:////tmp/projectverse-smoke.db \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8011 &
python ../scripts/smoke_api.py http://127.0.0.1:8011
```

The script checks health, readiness, project creation, reopening, a generated schedule, owner isolation, a JSON report, and deletion. Development mode accepts `X-Owner-Id`; production ignores it.

## Production check through Caddy

```bash
curl -sf https://projects.example.ir/health
curl -s -o /dev/null -w '%{http_code}\n' https://projects.example.ir/api/v1/projects   # 401 without a session
curl -s -c /tmp/pv.cookies -H 'Content-Type: application/json' -H 'X-Requested-With: fetch' \
  -d '{"email":"you@example.com","password":"…"}' https://projects.example.ir/api/v1/auth/login
curl -s -b /tmp/pv.cookies https://projects.example.ir/api/v1/projects
```
