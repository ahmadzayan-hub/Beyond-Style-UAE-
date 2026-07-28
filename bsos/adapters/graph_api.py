"""Meta Graph API adapter — the only lawful Instagram data path (P7).

Business Discovery, v25.0, Facebook Login path. Confirmed constraints coded
against here:
  - target must be a professional account; age-gated accounts return nothing
  - a direct GET on a returned media id fails on permissions, so every field
    comes through nested field expansion in the single business_discovery call
  - cursor pagination lives INSIDE the nested media object
  - app rate limit is ~200 calls/hour → token bucket at 150 with exponential
    backoff on 4xx/429, remaining budget surfaced for the UI
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

GRAPH_BASE = "https://graph.facebook.com/v25.0"

MEDIA_FIELDS = (
    "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count,"
    "children{id,media_type,media_url}"
)
PROFILE_FIELDS = (
    "username,name,biography,website,profile_picture_url,"
    "followers_count,follows_count,media_count"
)


class GraphAPIError(Exception):
    pass


class RateLimitExhausted(GraphAPIError):
    pass


@dataclass
class TokenBucket:
    capacity: int = 150
    refill_period_s: float = 3600.0
    tokens: float = field(default=-1.0)
    _last: float = field(default_factory=time.monotonic)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        if self.tokens < 0:
            self.tokens = float(self.capacity)

    def _refill(self) -> None:
        now = time.monotonic()
        self.tokens = min(
            float(self.capacity),
            self.tokens + (now - self._last) * (self.capacity / self.refill_period_s),
        )
        self._last = now

    def acquire(self) -> None:
        with self._lock:
            self._refill()
            if self.tokens < 1:
                raise RateLimitExhausted(
                    f"Graph API hourly budget exhausted ({self.capacity}/h); "
                    f"retry in ~{self.seconds_until_available():.0f}s"
                )
            self.tokens -= 1

    def seconds_until_available(self) -> float:
        return max(0.0, (1 - self.tokens) * (self.refill_period_s / self.capacity))

    @property
    def remaining(self) -> int:
        with self._lock:
            self._refill()
            return int(self.tokens)


class GraphClient:
    def __init__(
        self,
        access_token: str,
        ig_user_id: str,
        bucket: TokenBucket | None = None,
        transport: Callable[..., httpx.Response] | None = None,
        max_retries: int = 4,
    ):
        if not access_token or not ig_user_id:
            raise GraphAPIError("META_ACCESS_TOKEN / META_IG_USER_ID missing — see SETUP.md")
        self.access_token = access_token
        self.ig_user_id = ig_user_id
        self.bucket = bucket or TokenBucket()
        self._transport = transport or (lambda url, params: httpx.get(url, params=params, timeout=30))
        self.max_retries = max_retries

    # ------------------------------------------------------------------
    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "access_token": self.access_token}
        delay = 2.0
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self.bucket.acquire()
            try:
                resp = self._transport(url, params)
            except httpx.TransportError as exc:
                last_error = exc
                time.sleep(delay)
                delay *= 2
                continue
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429 or 400 <= resp.status_code < 500:
                last_error = GraphAPIError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                if attempt < self.max_retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
            else:
                resp.raise_for_status()
        raise GraphAPIError(f"Graph API call failed after {self.max_retries + 1} attempts: {last_error}")

    # ------------------------------------------------------------------
    def business_discovery(
        self, target_username: str, media_limit: int = 50, after: str | None = None
    ) -> dict[str, Any]:
        """One business_discovery call: profile + one page of nested media."""
        media_spec = f"media.limit({media_limit})"
        if after:
            media_spec += f".after({after})"
        fields = (
            f"business_discovery.username({target_username})"
            f"{{{PROFILE_FIELDS},{media_spec}{{{MEDIA_FIELDS}}}}}"
        )
        data = self._get(f"{GRAPH_BASE}/{self.ig_user_id}", {"fields": fields})
        bd = data.get("business_discovery")
        if not bd:
            raise GraphAPIError(
                f"no business_discovery data for '{target_username}' — target must be a "
                "professional (business/creator) account and not age-gated"
            )
        return bd

    def iter_media(self, target_username: str, max_items: int = 200, media_limit: int = 50):
        """Iterate media across pages using the cursor inside the nested media object."""
        fetched = 0
        after: str | None = None
        while fetched < max_items:
            bd = self.business_discovery(target_username, media_limit=media_limit, after=after)
            media = bd.get("media", {})
            for item in media.get("data", []):
                yield item
                fetched += 1
                if fetched >= max_items:
                    return
            after = media.get("paging", {}).get("cursors", {}).get("after")
            if not after:
                return

    def own_media(self, limit: int = 50) -> dict[str, Any]:
        """The brand's own media via /me-style edge (supplier-authorised OAuth mode)."""
        return self._get(
            f"{GRAPH_BASE}/{self.ig_user_id}/media",
            {"fields": MEDIA_FIELDS, "limit": limit},
        )
