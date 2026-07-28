"""Graph API adapter: cursor pagination inside nested media, backoff, budget."""

from __future__ import annotations

import json

import httpx
import pytest

import bsos.adapters.graph_api as graph_api
from bsos.adapters.graph_api import (
    GraphClient, GraphAPIError, RateLimitExhausted, TokenBucket,
)


def _response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, text=json.dumps(body))


def _bd_page(items: list[dict], after: str | None) -> dict:
    media: dict = {"data": items}
    if after:
        media["paging"] = {"cursors": {"after": after}}
    return {"business_discovery": {"username": "target", "media_count": 5, "media": media}}


def test_cursor_pagination_walks_nested_media_cursor():
    calls: list[dict] = []

    def transport(url, params):
        calls.append(params)
        fields = params["fields"]
        if ".after(CURSOR1)" in fields:
            return _response(200, _bd_page([{"id": "m3"}, {"id": "m4"}], None))
        return _response(200, _bd_page([{"id": "m1"}, {"id": "m2"}], "CURSOR1"))

    client = GraphClient("token", "1789", transport=transport)
    items = list(client.iter_media("target", max_items=10, media_limit=2))
    assert [i["id"] for i in items] == ["m1", "m2", "m3", "m4"]
    assert len(calls) == 2
    # Every field must come through nested expansion in the single request.
    assert "business_discovery.username(target)" in calls[0]["fields"]
    assert "media.limit(2)" in calls[0]["fields"]
    assert "children{id,media_type,media_url}" in calls[0]["fields"]


def test_backoff_on_429_then_success(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(graph_api.time, "sleep", sleeps.append)
    attempts = {"n": 0}

    def transport(url, params):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            return _response(429, {"error": {"message": "rate limited"}})
        return _response(200, _bd_page([{"id": "ok"}], None))

    client = GraphClient("token", "1789", transport=transport)
    bd = client.business_discovery("target")
    assert bd["media"]["data"][0]["id"] == "ok"
    assert sleeps == [2.0, 4.0]  # exponential backoff


def test_4xx_exhausts_retries_with_clear_error(monkeypatch):
    monkeypatch.setattr(graph_api.time, "sleep", lambda s: None)
    client = GraphClient(
        "token", "1789", max_retries=2,
        transport=lambda url, params: _response(400, {"error": {"message": "bad field"}}),
    )
    with pytest.raises(GraphAPIError, match="HTTP 400"):
        client.business_discovery("target")


def test_token_bucket_budget_and_exhaustion():
    bucket = TokenBucket(capacity=3)
    client = GraphClient(
        "token", "1789", bucket=bucket, max_retries=0,
        transport=lambda url, params: _response(200, _bd_page([{"id": "x"}], None)),
    )
    for _ in range(3):
        client.business_discovery("target")
    assert bucket.remaining == 0
    with pytest.raises(RateLimitExhausted):
        client.business_discovery("target")


def test_non_professional_account_reported():
    client = GraphClient(
        "token", "1789",
        transport=lambda url, params: _response(200, {"id": "1789"}),  # no business_discovery key
    )
    with pytest.raises(GraphAPIError, match="professional"):
        client.business_discovery("private_person")
