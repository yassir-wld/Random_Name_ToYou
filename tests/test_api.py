from datetime import datetime, timezone

from app.models import Check, Incident, Target


def seed(session):
    target = Target(slug="web", name="Website", url="https://example.org")
    session.add(target)
    session.flush()
    session.add(
        Check(
            target_id=target.id,
            checked_at=datetime.now(timezone.utc),
            success=True,
            status_code=200,
            response_ms=42.5,
        )
    )
    session.add(
        Incident(
            target_id=target.id,
            started_at=datetime.now(timezone.utc),
            reason="HTTP 503",
        )
    )
    session.commit()


def test_health_endpoint(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 200


def test_summary_and_history(client, session):
    seed(session)
    summary = client.get("/api/summary").json()
    assert summary[0]["slug"] == "web"
    assert summary[0]["availability_percent"] == 100
    assert summary[0]["response_ms"] == 42.5
    assert len(client.get("/api/targets/web/checks").json()) == 1
    assert client.get("/api/targets/missing/checks").status_code == 404


def test_incidents_filter(client, session):
    seed(session)
    result = client.get("/api/incidents?open_only=true").json()
    assert len(result) == 1
    assert result[0]["target"] == "web"


def test_prometheus_metrics(client, session):
    seed(session)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert 'opswatch_target_up{target="web"} 1.0' in response.text
    assert 'opswatch_target_latency_seconds{target="web"} 0.0425' in response.text
