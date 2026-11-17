# OpsWatch

A small service monitor with a separate polling worker, an HTTP API and a PostgreSQL database. It checks a list of URLs, keeps response history and records when a service goes down and recovers.

The project focuses on operating a service: containerised components, health probes, persistent data, automated tests and a CI pipeline.

## Stack

Python 3.12 · FastAPI · HTTPX · SQLAlchemy · PostgreSQL · Docker Compose · Prometheus · pytest · Ruff · GitHub Actions

## How it works

```text
                     +-------------------+
config/targets.json ->| monitoring worker |--- HTTP checks ---> targets
                     +---------+---------+
                               |
                               v
                         +-----------+
                         | PostgreSQL|
                         +-----+-----+
                               ^
                               |
                     +---------+---------+
                     |    FastAPI API    |<--- curl / browser
                     +---------+---------+
                               ^
                               |
                         Prometheus
                         (optional)
```

The worker checks services independently of API requests. A failed check opens an incident; the next successful check closes it. Response times and HTTP status codes are retained so failures can be investigated later.

## Run locally

Requires Docker with Compose v2.

```bash
cp .env.example .env
# Change POSTGRES_PASSWORD in .env for your environment.
docker compose up --build -d
docker compose ps
```

The API is available at <http://127.0.0.1:8000/docs>. The worker checks the local API and `example.org` by default. Allow about a minute for initial results to appear.

```bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
curl http://127.0.0.1:8000/api/summary
curl http://127.0.0.1:8000/api/targets
curl 'http://127.0.0.1:8000/api/targets/opswatch-api/checks?limit=10'
curl 'http://127.0.0.1:8000/api/incidents?open_only=true'
```

API docs: `/docs` · readiness: `/health/ready` · liveness: `/health/live` · Prometheus metrics: `/metrics`.

To enable Prometheus locally:

```bash
docker compose --profile monitoring up -d
# Prometheus UI: http://127.0.0.1:9090
```

Example PromQL queries: `opswatch_target_up` and `opswatch_target_latency_seconds`.

## Configure targets

Edit [`config/targets.json`](config/targets.json), then recreate the worker with `docker compose up --build -d worker`. Targets are configured by the operator rather than accepting arbitrary URLs through a public API. Each target has a name, URL, probe interval and timeout.

## Development and tests

Use Python 3.12 and a virtual environment. SQLite is used for local tests so a running PostgreSQL server is not necessary.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

The GitHub Actions workflow runs linting, tests and a Docker image build on every push or pull request. This is CI, not an automatic production deployment.

## Deployment notes

For a personal Linux VM, install Docker Compose, clone the repository, create `.env` on the machine and start the stack. Keep the API bound to localhost and put HTTPS and access control in front of it before making it public. Back up the `postgres_data` volume. For additional operational notes and known limitations, see [docs/operations.md](docs/operations.md).
