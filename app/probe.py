"""Make a single HTTP probe without relying on external scheduling code."""

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


@dataclass(frozen=True)
class ProbeResult:
    checked_at: datetime
    success: bool
    status_code: int | None
    response_ms: float | None
    error: str | None = None


def probe_url(client: httpx.Client, url: str, timeout: float) -> ProbeResult:
    started_at = time.perf_counter()
    checked_at = datetime.now(timezone.utc)
    try:
        response = client.get(url, timeout=timeout, follow_redirects=False)
        elapsed = round((time.perf_counter() - started_at) * 1000, 2)
        ok = 200 <= response.status_code < 400
        return ProbeResult(
            checked_at=checked_at,
            success=ok,
            status_code=response.status_code,
            response_ms=elapsed,
            error=None if ok else f"HTTP {response.status_code}",
        )
    except httpx.RequestError as exc:
        return ProbeResult(
            checked_at=checked_at,
            success=False,
            status_code=None,
            response_ms=None,
            error=type(exc).__name__,
        )
