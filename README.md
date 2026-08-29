# ⏱ Pulse Check

A tiny reaction-timing game for IBM Cloud Code Engine. Register a handle, then hit STOP as close to the target time as you can — scored by closeness, best score on your dashboard.

## Architecture

`Browser (vanilla JS timer)` → `Flask app (Code Engine)` → `PostgreSQL`

- **`src/main.py`** — Flask app: registration, score submission, dashboard, health.
- **`src/templates/index.html`** — single page: game + stats, no build chain.
- **`schema.sql`** — two tables (`players`, `attempts`), applied automatically at startup.
- **`Procfile`** — gunicorn start command for Cloud Native Buildpacks.

No Dockerfile — the app builds with Cloud Native Buildpacks straight from this repo.

## Running locally

```
pip install -r requirements.txt
export DATABASE_URL=postgres://user:pass@host:5432/dbname
python src/main.py
```

Without `DATABASE_URL` the app still starts: the dashboard shows a "waiting for a database" banner and `/health` reports degraded until a database is configured.

## Configuration

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (`sslmode=require` supported) |
| `PORT` | Listen port (default `8080`) |
| `INFERENCE_ENABLED` | `true` to enable the `/summary` endpoint (optional) |

## Endpoints

| Route | Description |
|---|---|
| `GET /` | Dashboard: register or play |
| `POST /register` | Create/update a player profile |
| `POST /score` | Record an attempt |
| `GET /health` | Liveness + DB connectivity check |
| `GET /summary` | AI summary of recent activity (feature-flagged) |

## Deploying to IBM Cloud Code Engine

Deploy as a Code Engine **application** built from this repo's source (buildpacks strategy), with `DATABASE_URL` supplied from a secret bound to a Databases for PostgreSQL instance:

```
ibmcloud ce app create --name pulse-check --build-source <this-repo-url> --strategy buildpacks --port 8080
```

The schema is applied automatically on first startup.
