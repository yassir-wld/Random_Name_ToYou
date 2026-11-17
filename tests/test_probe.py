import httpx

from app.probe import probe_url


def test_successful_probe_records_latency():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(204)))
    result = probe_url(client, "https://example.org", timeout=2)
    assert result.success is True
    assert result.status_code == 204
    assert result.response_ms >= 0
    assert result.error is None
    client.close()


def test_server_error_is_unhealthy():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    result = probe_url(client, "https://example.org", timeout=2)
    assert result.success is False
    assert result.status_code == 503
    assert result.error == "HTTP 503"
    client.close()


def test_network_error_does_not_crash_worker():
    def fail(request):
        raise httpx.ConnectError("No route to host", request=request)

    client = httpx.Client(transport=httpx.MockTransport(fail))
    result = probe_url(client, "https://example.org", timeout=2)
    assert result.success is False
    assert result.status_code is None
    assert result.error == "ConnectError"
    client.close()
