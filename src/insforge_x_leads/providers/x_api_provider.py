from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from ..models import XPost
from .base import ReadOnlyProvider


RECENT_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"


class XApiReadOnlyProvider(ReadOnlyProvider):
    name = "x_api"

    def __init__(self, bearer_token: str | None = None, *, retries: int = 3, timeout_seconds: int = 30) -> None:
        token = str(bearer_token or os.environ.get("X_BEARER_TOKEN", "")).strip()
        if not token:
            raise RuntimeError("X_BEARER_TOKEN is required for live official X API use")
        self.bearer_token = token
        self.retries = retries
        self.timeout_seconds = timeout_seconds

    def search_public_posts(self, queries: list[str], limit: int) -> list[XPost]:
        posts: list[XPost] = []
        per_query_limit = max(10, min(100, limit // max(len(queries), 1) or limit))
        for query in queries:
            remaining = max(0, limit - len(posts))
            if remaining <= 0:
                break
            posts.extend(self._search_query(query, min(per_query_limit, max(10, remaining))))
        return posts[:limit]

    def _search_query(self, query: str, limit: int) -> list[XPost]:
        params = {
            "query": query,
            "max_results": str(max(10, min(100, limit))),
            "tweet.fields": "author_id,created_at,public_metrics,lang",
            "expansions": "author_id",
            "user.fields": "username,name",
        }
        payload = self._get_json(f"{RECENT_SEARCH_URL}?{urllib.parse.urlencode(params)}")
        return _payload_to_posts(payload)

    def _get_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "User-Agent": "insforge-x-leads/1.0 read-only",
            },
            method="GET",
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429 or 500 <= exc.code < 600:
                    delay = _retry_delay_seconds(exc, attempt)
                    time.sleep(delay)
                    continue
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"X API HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                last_error = exc
                time.sleep(min(2**attempt, 30))
        raise RuntimeError(f"X API request failed after retries: {last_error}") from last_error


def _retry_delay_seconds(exc: urllib.error.HTTPError, attempt: int) -> float:
    reset = exc.headers.get("x-rate-limit-reset")
    if reset:
        try:
            reset_at = datetime.fromtimestamp(int(reset), timezone.utc)
            delay = (reset_at - datetime.now(timezone.utc)).total_seconds()
            return min(max(delay, 1), 900)
        except ValueError:
            pass
    return min(2**attempt, 30)


def _payload_to_posts(payload: dict[str, Any]) -> list[XPost]:
    users = {
        str(user.get("id")): user
        for user in payload.get("includes", {}).get("users", [])
        if isinstance(user, dict)
    }
    posts: list[XPost] = []
    for tweet in payload.get("data", []) or []:
        if not isinstance(tweet, dict):
            continue
        user = users.get(str(tweet.get("author_id")), {})
        username = str(user.get("username", ""))
        tweet_id = str(tweet.get("id", ""))
        metrics = tweet.get("public_metrics", {}) if isinstance(tweet.get("public_metrics"), dict) else {}
        posts.append(
            XPost(
                post_id=tweet_id,
                post_url=f"https://x.com/{username}/status/{tweet_id}" if username and tweet_id else "",
                author_handle=username,
                author_name=str(user.get("name", "")),
                text=str(tweet.get("text", "")),
                created_at=str(tweet.get("created_at", "")),
                metrics={
                    "reply_count": metrics.get("reply_count", 0),
                    "retweet_count": metrics.get("retweet_count", 0),
                    "like_count": metrics.get("like_count", 0),
                    "quote_count": metrics.get("quote_count", 0),
                },
                raw={"provider": "x_api", "id": tweet_id},
            )
        )
    return posts
