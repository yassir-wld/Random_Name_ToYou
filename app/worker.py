"""Poll configured services and track incident state transitions."""

import logging
import os
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import TargetConfig, load_targets
from app.db import SessionLocal, init_database
from app.models import Check, Incident, Target
from app.probe import ProbeResult, probe_url

logger = logging.getLogger("opswatch.worker")


def as_utc(value: datetime) -> datetime:
    # SQLite may return naive datetimes even when timezone=True is set.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def save_probe(session: Session, target: Target, result: ProbeResult) -> None:
    session.add(
        Check(
            target_id=target.id,
            checked_at=result.checked_at,
            success=result.success,
            status_code=result.status_code,
            response_ms=result.response_ms,
            error=result.error,
        )
    )
    target.last_checked_at = result.checked_at

    open_incident = session.scalars(
        select(Incident)
        .where(Incident.target_id == target.id, Incident.resolved_at.is_(None))
        .order_by(Incident.started_at.desc())
    ).first()
    if not result.success and open_incident is None:
        session.add(
            Incident(
                target_id=target.id,
                started_at=result.checked_at,
                reason=result.error or "Probe failed",
            )
        )
    elif result.success and open_incident is not None:
        open_incident.resolved_at = result.checked_at


def run_cycle(session: Session, configs: list[TargetConfig], client: httpx.Client) -> int:
    completed = 0
    now = datetime.now(timezone.utc)
    configured_slugs = {item.slug for item in configs}

    for existing in session.scalars(select(Target)).all():
        existing.enabled = existing.slug in configured_slugs

    for config in configs:
        target = session.scalar(select(Target).where(Target.slug == config.slug))
        if target is None:
            target = Target(slug=config.slug, name=config.name, url=config.url)
            session.add(target)
            session.flush()
        else:
            target.name = config.name
            target.url = config.url
            target.enabled = True

        if target.last_checked_at is not None:
            age = (now - as_utc(target.last_checked_at)).total_seconds()
            if age < config.interval_seconds:
                continue
        result = probe_url(client, config.url, config.timeout_seconds)
        save_probe(session, target, result)
        logger.info(
            "target=%s success=%s status=%s latency_ms=%s",
            target.slug,
            result.success,
            result.status_code,
            result.response_ms,
        )
        completed += 1
    session.commit()
    return completed


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    init_database()
    interval = int(os.getenv("WORKER_TICK_SECONDS", "10"))
    if interval < 1:
        raise ValueError("WORKER_TICK_SECONDS must be positive")
    with httpx.Client(headers={"User-Agent": "OpsWatch/1.0"}) as client:
        while True:
            try:
                targets = load_targets()
                with SessionLocal() as session:
                    run_cycle(session, targets, client)
            except (OSError, ValueError, httpx.HTTPError, RuntimeError):
                logger.exception("Monitoring cycle failed")
            time.sleep(interval)


if __name__ == "__main__":
    main()
