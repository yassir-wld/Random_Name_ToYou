"""Read-only API for service health and monitoring history."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import get_session, init_database
from app.models import Check, Incident, Target


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_database()
    yield


app = FastAPI(
    title="OpsWatch",
    description="Health checks, incident history and basic availability metrics.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health/live", tags=["health"])
def liveness() -> dict:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def readiness(session: Session = Depends(get_session)) -> dict:
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


@app.get("/api/targets", tags=["monitoring"])
def targets(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.scalars(select(Target).order_by(Target.slug)).all()
    return [
        {"slug": row.slug, "name": row.name, "url": row.url, "enabled": row.enabled}
        for row in rows
    ]


@app.get("/api/targets/{slug}/checks", tags=["monitoring"])
def target_checks(
    slug: str,
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[dict]:
    target = session.scalar(select(Target).where(Target.slug == slug))
    if target is None:
        raise HTTPException(status_code=404, detail="Unknown target")
    checks = session.scalars(
        select(Check)
        .where(Check.target_id == target.id)
        .order_by(Check.checked_at.desc(), Check.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "checked_at": check.checked_at,
            "success": check.success,
            "status_code": check.status_code,
            "response_ms": check.response_ms,
            "error": check.error,
        }
        for check in checks
    ]


@app.get("/api/incidents", tags=["monitoring"])
def incidents(
    open_only: bool = False, session: Session = Depends(get_session)
) -> list[dict]:
    statement = (
        select(Incident, Target.slug)
        .join(Target, Incident.target_id == Target.id)
        .order_by(Incident.started_at.desc(), Incident.id.desc())
    )
    if open_only:
        statement = statement.where(Incident.resolved_at.is_(None))
    rows = session.execute(statement.limit(100)).all()
    return [
        {
            "id": incident.id,
            "target": slug,
            "reason": incident.reason,
            "started_at": incident.started_at,
            "resolved_at": incident.resolved_at,
        }
        for incident, slug in rows
    ]


@app.get("/api/summary", tags=["monitoring"])
def summary(session: Session = Depends(get_session)) -> list[dict]:
    items = []
    for target in session.scalars(select(Target).where(Target.enabled.is_(True))).all():
        latest = session.scalar(
            select(Check)
            .where(Check.target_id == target.id)
            .order_by(Check.checked_at.desc(), Check.id.desc())
            .limit(1)
        )
        total, successful = session.execute(
            select(func.count(Check.id), func.count(Check.id).filter(Check.success.is_(True)))
            .where(Check.target_id == target.id)
        ).one()
        items.append(
            {
                "slug": target.slug,
                "up": latest.success if latest else None,
                "status_code": latest.status_code if latest else None,
                "response_ms": latest.response_ms if latest else None,
                "last_checked_at": latest.checked_at if latest else None,
                "checks": total,
                "availability_percent": round(successful * 100 / total, 2)
                if total else None,
            }
        )
    return sorted(items, key=lambda item: item["slug"])


@app.get("/metrics", include_in_schema=False)
def metrics(session: Session = Depends(get_session)) -> Response:
    registry = CollectorRegistry()
    up_gauge = Gauge(
        "opswatch_target_up", "Latest HTTP check succeeded", ["target"], registry=registry
    )
    latency_gauge = Gauge(
        "opswatch_target_latency_seconds",
        "Latency of the latest check", ["target"], registry=registry
    )
    for item in summary(session):
        if item["up"] is not None:
            up_gauge.labels(target=item["slug"]).set(int(item["up"]))
        if item["response_ms"] is not None:
            latency_gauge.labels(target=item["slug"]).set(item["response_ms"] / 1000)
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
