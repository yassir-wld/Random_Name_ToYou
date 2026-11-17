import httpx
from sqlalchemy import select

from app.config import TargetConfig
from app.models import Check, Incident, Target
from app.worker import run_cycle


CONFIG = TargetConfig(
    slug="app-demo", name="Application", url="https://example.org", interval_seconds=5
)


def make_client(status_code):
    return httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(status_code))
    )


def test_incident_opens_and_resolves(session):
    with make_client(503) as http_client:
        assert run_cycle(session, [CONFIG], http_client) == 1
    incident = session.scalars(select(Incident)).one()
    assert incident.resolved_at is None
    assert len(session.scalars(select(Check)).all()) == 1

    target = session.scalars(select(Target)).one()
    target.last_checked_at = None  # the next scheduled cycle is due
    session.commit()
    with make_client(200) as http_client:
        assert run_cycle(session, [CONFIG], http_client) == 1

    session.refresh(incident)
    assert incident.resolved_at is not None
    assert len(session.scalars(select(Incident)).all()) == 1
    assert len(session.scalars(select(Check)).all()) == 2


def test_skip_target_until_next_interval(session):
    with make_client(200) as http_client:
        assert run_cycle(session, [CONFIG], http_client) == 1
        assert run_cycle(session, [CONFIG], http_client) == 0
    assert session.query(Check).count() == 1


def test_removed_targets_are_disabled(session):
    with make_client(200) as http_client:
        run_cycle(session, [CONFIG], http_client)
        run_cycle(session, [], http_client)
    assert session.scalar(select(Target)).enabled is False
