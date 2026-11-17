# Operations notes

## Architecture

An API container serves read-only status endpoints. A worker container probes the configured HTTP services and records results in PostgreSQL. Both use the same database. Prometheus can scrape the API, which builds metrics from the stored latest check for each target.

A failed check creates an incident if none is open. A successful check closes the incident. Transient failures therefore appear in incident history, not just in logs.

## Change the monitored services

Edit `config/targets.json` and rebuild/recreate the worker container:

```bash
docker compose up --build -d worker
```

Use a stable `slug` for each service. Removing an entry disables the service in the API; past checks and incidents remain available.

## Debugging

```bash
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 worker
docker compose exec db pg_isready -U opswatch -d opswatch
```

When the worker reports `ConnectError`, check whether the target hostname resolves from inside its container. `localhost` inside a container is not the host machine; use the Compose service name for internal traffic.

## Boundaries

This is a portfolio deployment, not a hosted monitoring platform. The API is intentionally read-only; targets are configured in a versioned JSON file. Table creation uses SQLAlchemy metadata, not a migration system. There is no retention policy, alert notification, multi-worker lock, TLS termination, or automated cloud provisioning. Add migrations, HTTPS, alerting and a backup/restore plan before any shared production deployment.

The example Compose configuration publishes ports only on `127.0.0.1`. Never expose PostgreSQL publicly. Do not check `.env` or credentials into git.
