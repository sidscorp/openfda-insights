import httpx
import pytest

from enhanced_fda_explorer.openfda_client import OpenFDAClient


def test_client_injects_api_key_and_sort():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_key"] == "token-123"
        assert request.url.params["sort"] == "date_received:desc"
        assert request.url.params["search"] == "brand:mask"
        return httpx.Response(200, json={"results": [{"ok": True}], "meta": {"results": {"total": 1}}})

    transport = httpx.MockTransport(handler)
    client = OpenFDAClient(
        base_url="https://api.fda.gov/",
        api_key="token-123",
        max_retries=0,
        sync_transport=transport,
    )

    data = client.get("device/event.json", params={"search": "brand:mask"}, sort="date_received:desc")
    assert data["results"] == [{"ok": True}]


def test_client_retries_on_429_then_succeeds():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"results": [{"ok": True}], "meta": {"results": {"total": 1}}})

    transport = httpx.MockTransport(handler)
    client = OpenFDAClient(
        base_url="https://api.fda.gov/",
        api_key=None,
        max_retries=1,
        rate_limit_delay=0.01,
        sync_transport=transport,
    )

    data = client.get("device/event.json", params={"search": "mask"})
    assert data["results"][0]["ok"] is True
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_async_pagination_combines_results():
    def handler(request: httpx.Request) -> httpx.Response:
        skip = int(request.url.params.get("skip", 0))
        limit = int(request.url.params.get("limit", 0))
        # Return predictable slices to verify aggregation
        results = [{"idx": i} for i in range(skip, skip + limit)]
        return httpx.Response(200, json={"results": results, "meta": {"results": {"total": 200}}})

    transport = httpx.MockTransport(handler)
    client = OpenFDAClient(
        base_url="https://api.fda.gov/",
        api_key=None,
        max_retries=0,
        async_transport=transport,
    )

    data = await client.aget_paginated(
        "device/event.json",
        params={"search": "mask"},
        limit=120,
        sort="date_received:desc",
        page_size=50,
    )

    assert len(data["results"]) == 120
    # Ensure results are contiguous and include the last index requested
    assert data["results"][0]["idx"] == 0
    assert data["results"][-1]["idx"] == 119
