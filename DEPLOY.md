# Deploying ProjectVerseAI on an Iranian VPS

**خلاصهٔ فارسی:** ProjectVerse روی یک سرور مجازی ایرانی با Docker Compose اجرا می‌شود و پشت **همان Caddy مشترک** پلتفرم‌های دیگر (مثل ElectionSimulationAI) روی یک زیردامنه مانند `projects.example.ir` قرار می‌گیرد. این پروژه هیچ پورتی روی سرور باز نمی‌کند. پایگاه داده یا داخل همین پروژه است (پیش‌فرض) یا Postgres مشترک سرور. رمزها فقط در فایل `.env` روی سرور هستند. زبان پیش‌فرض رابط کاربری انگلیسی است و با دکمهٔ «فارسی» در بالای صفحه به فارسی (راست‌به‌چپ، تاریخ شمسی، تومان/ریال) تغییر می‌کند و انتخاب کاربر ذخیره می‌شود. کاربران را فقط مدیر می‌سازد؛ ثبت‌نام عمومی وجود ندارد.

The rest of this guide is in English so commands can be copied exactly. It follows the same server conventions as ElectionSimulationAI's `DEPLOY.md`: one external Docker network `caddy`, one shared Caddy container, one subdomain per platform, optional shared PostgreSQL on an external network `postgres`.

## 0. What you need

| Item | Notes |
|---|---|
| Iranian VPS | Ubuntu 22.04/24.04 or Debian 12. This app alone needs about 1 GB RAM (the first image build needs more; add swap). |
| Domain | One subdomain, e.g. `projects.example.ir`, with an `A` record to the VPS IPv4. |
| Docker | Docker Engine with Compose **2.24.4 or newer** (`docker compose version`), needed for `!override` in the shared-db overlay. |
| Shared Caddy | Already set up once per server. If not, follow step 1 of ElectionSimulationAI's `DEPLOY.md` (network `caddy`, Caddy compose in `/srv/caddy`). The commands are repeated briefly below. |

## 1. Server prerequisites (once per server, shared by every platform)

Skip anything already done for another platform.

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 || sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw enable
docker network create caddy
```

### Docker Hub / PyPI / npm from Iran

Docker Hub refuses pulls from Iranian IP addresses, and PyPI/npm can be slow or blocked. Use Iranian mirrors. These were listed in provider documentation on 16 Oct 2026; check they still work:

```bash
sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.bak 2>/dev/null || true
echo '{ "registry-mirrors": ["https://docker.arvancloud.ir", "https://docker-mirror.liara.ir", "https://hub.hamdocker.ir"] }' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
```

In `.env` (step 3), for the image builds:

```
PIP_INDEX_URL=https://package-mirror.liara.ir/repository/pypi/simple
NPM_REGISTRY=https://package-mirror.liara.ir/repository/npm/
```

You can also point base images straight at a mirror registry instead of configuring the daemon, for example `POSTGRES_IMAGE=docker.arvancloud.ir/postgres:16-alpine`, `PYTHON_IMAGE=docker.arvancloud.ir/python:3.12-slim`, `NODE_IMAGE=docker.arvancloud.ir/node:22-alpine`.

The frontend does not download Google Fonts at build time (it uses system fonts with Vazirmatn/Tahoma fallbacks for Persian), so the build has no dependency on fonts.googleapis.com.

A mirror is a third party. Alternatively build the images elsewhere, `docker save` them, copy with `scp`, and `docker load` on the VPS.

## 2. Add the site to the shared Caddy

Append this block to `/srv/caddy/Caddyfile` (a copy is in `deploy/Caddyfile.shared.example`), replacing the hostname:

```
projects.example.ir {
	encode gzip
	header {
		Strict-Transport-Security "max-age=31536000; includeSubDomains"
		X-Content-Type-Options nosniff
		Referrer-Policy no-referrer
		X-Frame-Options DENY
		-Server
	}
	handle /api/* {
		reverse_proxy projectverse-api:8000 {
			header_up X-Forwarded-For {remote_host}
			header_up X-Real-IP {remote_host}
		}
	}
	handle {
		reverse_proxy projectverse-web:3000 {
			header_up X-Forwarded-For {remote_host}
			header_up X-Real-IP {remote_host}
			health_uri /health
			health_interval 30s
		}
	}
}
```

Reload after the app is running (step 4): `docker exec caddy caddy reload --config /etc/caddy/Caddyfile`.

The browser talks to one origin (`https://projects.example.ir`). Caddy sends `/api/*` to the API container and everything else to the Next.js container, so the sign-in cookie is first-party and no cross-origin requests are needed.

## 3. Get the code and configure `.env`

```bash
sudo mkdir -p /srv/projectverse && sudo chown "$USER" /srv/projectverse
git clone https://github.com/meysamghf-spec/ProjectVerseAI.git /srv/projectverse
cd /srv/projectverse
cp .env.example .env && chmod 600 .env
openssl rand -base64 36 | tr -d '/+=@:?#'   # once per secret
```

Set at least:

```
SITE_ADDRESS=projects.example.ir
POSTGRES_PASSWORD=<long random value, at least 16 characters, no @ : / ? #>
INITIAL_ADMIN_EMAIL=you@example.com
INITIAL_ADMIN_PASSWORD=<long random value, at least 10 characters>
DEFAULT_LOCALE=en        # or fa to show Persian to first-time visitors
PIP_INDEX_URL=           # mirrors from step 1, if needed
NPM_REGISTRY=
```

`.env` is git-ignored. Never commit it. Leave `LLM_API_KEY` empty: the built-in deterministic parser understands English and Persian descriptions (e.g. «برج مسکونی ۲۰ طبقه با ۳ طبقه زیرزمین، ۲۵٬۰۰۰ متر مربع، بودجه ۵۰۰ میلیارد تومان، ۳۰ ماه») and OpenAI-style providers are not reachable from Iran.

The production compose file always sets `APP_ENV=production`, `AUTH_MODE=accounts`, secure cookies, and `CORS_ORIGINS=https://$SITE_ADDRESS`. The API refuses project requests if the production configuration is weak (short database password, wildcard CORS, other auth modes).

## 4. Start

Bundled database (simplest):

```bash
docker compose --profile production up -d --build
docker compose --profile production ps        # all three should become "healthy"
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

Shared PostgreSQL instead (one Postgres container for all platforms, on external network `postgres`, no published port):

```bash
docker exec -it postgres psql -U postgres \
  -c "CREATE ROLE projectverse LOGIN PASSWORD '<long password>';" \
  -c "CREATE DATABASE projectverse OWNER projectverse ENCODING 'UTF8' TEMPLATE template0;"
# in .env:
#   DATABASE_URL=postgresql+psycopg://projectverse:<long password>@postgres:5432/projectverse
#   SHARED_DB_NETWORK=postgres
docker compose -f docker-compose.yml -f docker-compose.shared-db.yml --profile production up -d --build
```

The database must be UTF-8 (the bundled one is created with `--encoding=UTF8`) so Persian project names, descriptions, and search work.

What runs where:

| Container | Networks | Host ports |
|---|---|---|
| `db` (bundled mode only) | `data` (internal, no internet) | none |
| `api` (FastAPI) | `data` (or shared `postgres`) + `internal` + shared `caddy` as `projectverse-api` | none |
| `web` (Next.js) | `internal` + shared `caddy` as `projectverse-web` | none |

Only the shared Caddy publishes ports. The API container runs `alembic upgrade head` before it starts.

## 5. Users and sign-in

1. Open `https://projects.example.ir` and sign in with `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD`. The admin is created only when the users table is empty.
2. Remove `INITIAL_ADMIN_PASSWORD` from `.env` and run `docker compose --profile production up -d` again.
3. Add users from **Users** in the header (admins only), or from the shell:
   ```bash
   docker compose --profile production exec -e CREATE_USER_EMAIL=a@b.ir -e CREATE_USER_PASSWORD='…' -e CREATE_USER_ROLE=user api python -m app.cli create-user
   ```
4. Each user sees only their own projects. Admins can disable users, reset passwords, and change roles; the last active admin cannot be removed.
5. If you used the old shared `API_KEY` mode, set `LEGACY_OWNER_ID=api-owner` (or your old `API_OWNER_ID`) before the first start so those projects move to the first admin.

Passwords are stored as scrypt hashes. Sessions last `SESSION_HOURS` (default 12) and are stored hashed in the database; changing a password signs out the other sessions. There is no public sign-up, email verification, or password reset by email (no SMTP). Repeated failed sign-ins are throttled per email and per client address in memory (reset when the API restarts).

## 6. Health checks and monitoring

| URL | Meaning |
|---|---|
| `https://projects.example.ir/health` | 200 `{"status":"ok","web":"ok","api":"ok"}` when the site, API, and database are up; 503 otherwise. Use it for uptime monitors. |
| `https://projects.example.ir/api/v1/health`, `/api/v1/ready` | API liveness and readiness (readiness checks the database). |
| `http://api:8000/health` (inside Docker) | API + database check, used by the container health check. |

```bash
docker compose --profile production logs -f --tail=100 api web
```

## 7. Updates, backups, rollback

```bash
cd /srv/projectverse && git pull && docker compose --profile production up -d --build
# bundled database backup:
docker compose --profile production exec -T db pg_dump -U projectverse -d projectverse -Fc > /var/backups/projectverse-$(date +%F).dump
# restore into a scratch container to prove the dump is usable before you need it
```

Copy dumps off the VPS. For a shared Postgres, run `pg_dump` in the shared container. Rollback: `git checkout <previous commit>` and `up -d --build`; migrations only add tables and columns.

## 8. Language, dates, and money

- The interface defaults to **English** (left-to-right, Gregorian dates, USD by default). The header toggle switches to **فارسی** (right-to-left, Jalali dates such as ۱۴۰۵/۰۷/۲۴, Persian digits). The choice is saved in the browser (localStorage and a `projectverse_locale` cookie).
- Currency is per project (USD, EUR, GBP, AED, TRY, IRR …). In Persian, IRR amounts are shown in toman by default or rial (Settings). Amounts are stored in rial; one toman is ten rial.
- The cost engine's sample unit rates are in USD. For a non-USD project, enter "USD exchange rate" on the create page to convert estimates; otherwise the project shows a warning that costs are unconverted USD sample rates.
- The project list, create page, dashboard, schedule labels, settings, sign-in, and users pages are translated. Some detailed screens (tasks, risks, scenarios, simulation, 3D, reports) still show English labels inside the Persian layout.

## 9. Local development

`docker compose -f docker-compose.dev.yml up --build` starts a laptop-only stack on 127.0.0.1:3000 / :8000 / :5432 in development mode (no sign-in). Never expose it to the internet.
